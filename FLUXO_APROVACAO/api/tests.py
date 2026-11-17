"""
Testes da API.  Rodar:  python manage.py test
(sem broker configurado o Celery roda em modo síncrono, então as
notificações são geradas na hora e dá pra testar o fluxo inteiro)
"""
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from SISTEMA.models import (
    Assinatura,
    Empresa,
    EtapaFluxo,
    FluxoInstancia,
    FluxoPadrao,
    Notificacao,
    Setor,
    Usuario,
)

SENHA = "SenhaForte#2026"


class ClienteComEventos(APIClient):
    """Executa os callbacks on_commit (publicação no broker) dentro do TestCase."""
    caso = None

    def generic(self, *args, **kwargs):
        with self.caso.captureOnCommitCallbacks(execute=True):
            return super().generic(*args, **kwargs)


def criar_usuario(empresa, username, perfil="padrao", setor=None):
    u = Usuario(username=username, email=f"{username}@x.com", empresa=empresa, perfil=perfil, setor=setor)
    u.set_password(SENHA)
    u.save()
    return u


class BaseAPITest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(nome="Champion")
        Assinatura.objects.create(empresa=self.empresa, plano="ouro", status="ativo",
                                  data_inicio=timezone.localdate())
        self.engenharia = Setor.objects.create(empresa=self.empresa, nome="Engenharia")
        self.financeiro = Setor.objects.create(empresa=self.empresa, nome="Financeiro")
        self.admin = criar_usuario(self.empresa, "admin", "administrador")
        self.eng = criar_usuario(self.empresa, "eng", setor=self.engenharia)
        self.fin = criar_usuario(self.empresa, "fin", setor=self.financeiro)

        self.modelo = FluxoPadrao.objects.create(empresa=self.empresa, nome="Compra", criado_por=self.admin)
        EtapaFluxo.objects.create(fluxo=self.modelo, ordem_etapa=1, nome="Análise técnica", setor=self.engenharia)
        EtapaFluxo.objects.create(fluxo=self.modelo, ordem_etapa=2, nome="Aprovação financeira", setor=self.financeiro)
        EtapaFluxo.objects.create(fluxo=self.modelo, ordem_etapa=3, nome="Diretoria",
                                  perfil_aprovador="administrador")

        # outra empresa, para testar isolamento
        self.outra = Empresa.objects.create(nome="Concorrente")
        self.intruso = criar_usuario(self.outra, "intruso", "administrador")

    def cliente(self, user):
        c = ClienteComEventos()
        c.caso = self
        r = c.post("/api/v1/auth/login/", {"username": user.username, "password": SENHA}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        return c

    def criar_fluxo(self, user=None):
        r = self.cliente(user or self.eng).post(
            "/api/v1/fluxos/", {"modelo": self.modelo.id, "nome": "Compra de chapas"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        return r.data


class AuthTests(BaseAPITest):
    def test_login_retorna_tokens_e_usuario(self):
        r = APIClient().post("/api/v1/auth/login/", {"username": "eng", "password": SENHA}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("access", r.data)
        self.assertIn("refresh", r.data)
        self.assertEqual(r.data["usuario"]["empresa"]["nome"], "Champion")

    def test_sem_token_401(self):
        self.assertEqual(APIClient().get("/api/v1/fluxos/").status_code, 401)

    def test_registro_cria_empresa_admin_e_freemium(self):
        r = APIClient().post("/api/v1/auth/registro/", {
            "empresa_nome": "Nova Ltda", "username": "dono", "email": "dono@nova.com",
            "password": SENHA}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        dono = Usuario.objects.get(username="dono")
        self.assertEqual(dono.perfil, "administrador")
        self.assertEqual(dono.empresa.plano_atual, "freemium")

    def test_me(self):
        r = self.cliente(self.fin).get("/api/v1/auth/me/")
        self.assertEqual(r.data["setor_detalhe"]["nome"], "Financeiro")
        self.assertFalse(r.data["is_admin"])


class FluxoTests(BaseAPITest):
    def test_fluxo_completo_com_permissoes_e_notificacoes(self):
        fluxo = self.criar_fluxo()
        fid = fluxo["id"]
        self.assertEqual(fluxo["etapa_atual"]["nome"], "Análise técnica")
        self.assertEqual([e["status"] for e in fluxo["etapas"]], ["atual", "pendente", "pendente"])

        # Financeiro não pode aprovar etapa da Engenharia
        r = self.cliente(self.fin).post(f"/api/v1/fluxos/{fid}/avancar/", {}, format="json")
        self.assertEqual(r.status_code, 403)

        # Engenharia aprova
        r = self.cliente(self.eng).post(f"/api/v1/fluxos/{fid}/avancar/", {"comentario": "ok"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data["etapa_atual"]["nome"], "Aprovação financeira")

        # Mensageria: o financeiro recebeu notificação de pendência
        self.assertTrue(Notificacao.objects.filter(usuario=self.fin, tipo="etapa_pendente").exists())
        pend = self.cliente(self.fin).get("/api/v1/fluxos/pendentes/")
        self.assertEqual([f["id"] for f in pend.data["results"]], [fid])

        # Financeiro devolve para a engenharia
        r = self.cliente(self.fin).post(f"/api/v1/fluxos/{fid}/retornar/", {"comentario": "faltou orçamento"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["etapa_atual"]["nome"], "Análise técnica")

        self.cliente(self.eng).post(f"/api/v1/fluxos/{fid}/avancar/", {}, format="json")
        self.cliente(self.fin).post(f"/api/v1/fluxos/{fid}/avancar/", {}, format="json")

        # Etapa 3 é só de administrador
        r = self.cliente(self.fin).post(f"/api/v1/fluxos/{fid}/avancar/", {}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertTrue(Notificacao.objects.filter(usuario=self.admin, tipo="etapa_pendente").exists())

        r = self.cliente(self.admin).post(f"/api/v1/fluxos/{fid}/avancar/", {}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "finalizado")
        self.assertTrue(Notificacao.objects.filter(usuario=self.eng, tipo="fluxo_finalizado").exists())

        # Histórico completo: criação + 5 movimentações
        self.assertEqual(len(r.data["movimentacoes"]), 6)

        # fluxo finalizado não movimenta mais
        r = self.cliente(self.admin).post(f"/api/v1/fluxos/{fid}/avancar/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_nao_retorna_da_primeira_etapa(self):
        fid = self.criar_fluxo()["id"]
        r = self.cliente(self.eng).post(f"/api/v1/fluxos/{fid}/retornar/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_etapa_id_desatualizado(self):
        fluxo = self.criar_fluxo()
        segunda = fluxo["etapas"][1]["id"]
        r = self.cliente(self.admin).post(f"/api/v1/fluxos/{fluxo['id']}/avancar/", {"etapa_id": segunda}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_filtros_lista(self):
        self.criar_fluxo()
        c = self.cliente(self.admin)
        self.assertEqual(c.get("/api/v1/fluxos/?status=em_andamento").data["count"], 1)
        self.assertEqual(c.get("/api/v1/fluxos/?status=finalizado").data["count"], 0)
        self.assertEqual(c.get("/api/v1/fluxos/?minhas=true").data["count"], 0)

    def test_so_admin_exclui_fluxo(self):
        fid = self.criar_fluxo()["id"]
        self.assertEqual(self.cliente(self.eng).delete(f"/api/v1/fluxos/{fid}/").status_code, 403)
        self.assertEqual(self.cliente(self.admin).delete(f"/api/v1/fluxos/{fid}/").status_code, 204)

    def test_notificacoes_contagem_e_leitura(self):
        fid = self.criar_fluxo()["id"]
        self.cliente(self.eng).post(f"/api/v1/fluxos/{fid}/avancar/", {}, format="json")
        c = self.cliente(self.fin)
        self.assertEqual(c.get("/api/v1/notificacoes/nao-lidas/").data["nao_lidas"], 1)
        c.post("/api/v1/notificacoes/ler-todas/")
        self.assertEqual(c.get("/api/v1/notificacoes/nao-lidas/").data["nao_lidas"], 0)


    def test_evento_atrasado_na_fila_nao_gera_pendencia_errada(self):
        """Se o worker processa o 'criado' depois que o fluxo já andou, não avisa ninguém errado."""
        from SISTEMA.tasks import processar_evento_fluxo
        fluxo = self.criar_fluxo()
        primeira = fluxo["etapas"][0]["id"]
        self.cliente(self.eng).post(f"/api/v1/fluxos/{fluxo['id']}/avancar/", {}, format="json")
        Notificacao.objects.all().delete()
        processar_evento_fluxo("criado", fluxo["id"], self.eng.id, primeira)
        self.assertFalse(Notificacao.objects.filter(tipo="etapa_pendente").exists())


class MultiEmpresaTests(BaseAPITest):
    def test_isolamento_entre_empresas(self):
        fid = self.criar_fluxo()["id"]
        c = self.cliente(self.intruso)
        self.assertEqual(c.get("/api/v1/fluxos/").data["count"], 0)
        self.assertEqual(c.get(f"/api/v1/fluxos/{fid}/").status_code, 404)
        self.assertEqual(c.post(f"/api/v1/fluxos/{fid}/avancar/", {}, format="json").status_code, 404)
        self.assertEqual(c.get("/api/v1/setores/").data["count"], 0)
        self.assertEqual(c.get("/api/v1/usuarios/").data["count"], 1)
        r = c.post("/api/v1/fluxos/", {"modelo": self.modelo.id, "nome": "x"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_nao_usa_setor_de_outra_empresa(self):
        r = self.cliente(self.intruso).post("/api/v1/usuarios/", {
            "username": "novo", "password": SENHA, "setor": self.engenharia.id}, format="json")
        self.assertEqual(r.status_code, 400)


class CadastroTests(BaseAPITest):
    def test_padrao_nao_cria_setor(self):
        r = self.cliente(self.eng).post("/api/v1/setores/", {"nome": "RH"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_admin_cria_modelo_com_etapas(self):
        r = self.cliente(self.admin).post("/api/v1/modelos/", {
            "nome": "Férias", "etapas": [
                {"nome": "Gestor", "setor": self.engenharia.id},
                {"nome": "RH", "perfil_aprovador": "administrador"},
            ]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual([e["ordem_etapa"] for e in r.data["etapas"]], [1, 2])

    def test_limite_de_usuarios_do_plano(self):
        Assinatura.objects.filter(empresa=self.empresa).update(plano="freemium")
        r = self.cliente(self.admin).post("/api/v1/usuarios/", {"username": "extra", "password": SENHA}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("plano", str(r.data).lower())


class EventosPagamentoTests(BaseAPITest):
    """Consumidor da fila flow.assinaturas (eventos vindos do microserviço de pagamentos)."""

    def evento(self, status, cobranca="c-1", plano="prata"):
        return {"evento": f"pagamento.{status}", "status": status, "cobranca_id": cobranca,
                "plano": plano, "valor": 8990, "empresa_id": self.empresa.id, "usuario_id": self.admin.id}

    def test_pago_ativa_plano_e_e_idempotente(self):
        from SISTEMA.assinaturas import aplicar_evento_pagamento
        self.assertIn("ativado", aplicar_evento_pagamento(self.evento("pago")))
        self.assertEqual(self.empresa.plano_atual, "prata")
        self.assertIn("já processado", aplicar_evento_pagamento(self.evento("pago")))
        self.assertEqual(self.empresa.assinaturas.filter(status="ativo").count(), 1)

    def test_reembolso_volta_para_freemium(self):
        from SISTEMA.assinaturas import aplicar_evento_pagamento
        Assinatura.objects.filter(empresa=self.empresa).delete()
        aplicar_evento_pagamento(self.evento("pago"))
        aplicar_evento_pagamento(self.evento("reembolsado"))
        self.assertEqual(self.empresa.plano_atual, "freemium")

    def test_status_sem_efeito_no_plano(self):
        from SISTEMA.assinaturas import aplicar_evento_pagamento
        self.assertIn("ignorado", aplicar_evento_pagamento(self.evento("pendente")))

    def test_token_tem_claims_para_o_microservico(self):
        from rest_framework_simplejwt.tokens import AccessToken
        r = APIClient().post("/api/v1/auth/login/", {"username": "admin", "password": SENHA}, format="json")
        t = AccessToken(r.data["access"])
        self.assertEqual(t["empresa_id"], self.empresa.id)
        self.assertEqual(t["perfil"], "administrador")
        self.assertEqual(t["empresa_nome"], "Champion")
        self.assertEqual(t["email"], "admin@x.com")


class WebTests(BaseAPITest):
    def login_web(self, user):
        self.client.post("/login/", {"username": user.username, "password": SENHA})
        self.assertIn("_auth_user_id", self.client.session)

    def test_colaborador_entra_e_ve_fluxos_mas_nao_gestao(self):
        self.criar_fluxo()
        self.login_web(self.fin)
        self.assertContains(self.client.get("/fluxos/instancias/"), "Compra de chapas")
        r = self.client.get("/setores/")
        self.assertRedirects(r, "/")
        self.assertEqual(self.client.get("/users/").status_code, 302)

    def test_colaborador_aprova_pelo_web_e_ve_notificacao(self):
        fid = self.criar_fluxo()["id"]
        inst = FluxoInstancia.objects.get(pk=fid)
        self.login_web(self.eng)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"/fluxos/instancias/{fid}/mover/{inst.etapa_atual.id}/", {"acao": "avancar"})
        self.assertEqual(inst.etapa_atual.nome, "Aprovação financeira")
        self.client.logout()
        self.login_web(self.fin)
        self.assertContains(self.client.get("/"), "aguardando sua aprovação")
        self.assertContains(self.client.get("/notificacoes/"), "Aprovação pendente")

    def test_colaborador_nao_aprova_etapa_de_outro_setor(self):
        fid = self.criar_fluxo()["id"]
        inst = FluxoInstancia.objects.get(pk=fid)
        self.login_web(self.fin)
        self.client.post(f"/fluxos/instancias/{fid}/mover/{inst.etapa_atual.id}/", {"acao": "avancar"})
        self.assertEqual(inst.etapa_atual.nome, "Análise técnica")

    def test_admin_ve_so_dados_da_empresa(self):
        Setor.objects.create(empresa=self.outra, nome="Setor secreto")
        self.login_web(self.admin)
        r = self.client.get("/setores/")
        self.assertContains(r, "Engenharia")
        self.assertNotContains(r, "Setor secreto")

    def test_planos_chama_microservico(self):
        from unittest.mock import patch
        self.login_web(self.admin)
        cob = {"id": "x", "plano": "prata", "valor_formatado": "R$ 89,90", "status": "pendente",
               "checkout_url": "http://pag/simulador/x/", "criado_em": "2026-11-10T10:00:00"}
        with patch("SISTEMA.pagamentos_client.listar_cobrancas", return_value=[cob]):
            self.assertContains(self.client.get("/assinatura/"), "R$ 89,90")
        with patch("SISTEMA.pagamentos_client.criar_cobranca", return_value=cob) as m:
            r = self.client.post("/checkout/prata/")
            self.assertEqual(r.url, "http://pag/simulador/x/")
            self.assertEqual(m.call_args.args[1], "prata")

    def test_planos_com_microservico_fora_do_ar(self):
        self.login_web(self.admin)
        with self.settings(PAGAMENTOS_URL="http://127.0.0.1:9"):
            self.assertContains(self.client.get("/assinatura/"), "fora do ar")


class SchemaTests(TestCase):
    def test_swagger_gera(self):
        r = self.client.get("/api/v1/schema/")
        self.assertEqual(r.status_code, 200)
