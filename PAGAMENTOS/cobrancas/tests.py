"""Testes do microserviço de pagamentos.  Rodar: python manage.py test"""
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from kombu import Connection
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from . import mensageria, services
from .emails import enviar_email_status
from .models import Cobranca


def token(perfil="administrador", empresa_id=1, user_id=10):
    t = AccessToken()
    t["user_id"] = user_id
    t["empresa_id"] = empresa_id
    t["empresa_nome"] = "Champion"
    t["perfil"] = perfil
    t["email"] = "admin@champion.com"
    t["nome"] = "João"
    return str(t)


def cliente(**kw):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {token(**kw)}")
    return c


@override_settings(SIMULADOR_ATIVO=True, PUBLIC_URL="http://localhost:8000")
class CobrancaTests(TestCase):
    def setUp(self):
        self.eventos = []
        p = patch("cobrancas.mensageria.publicar", side_effect=self.eventos.append)
        p.start()
        self.addCleanup(p.stop)

    def criar(self, c=None, plano="prata"):
        with self.captureOnCommitCallbacks(execute=True):
            r = (c or cliente()).post("/api/pagamentos/cobrancas/", {"plano": plano}, format="json")
        return r

    def test_admin_cria_cobranca_e_publica_pendente(self):
        r = self.criar()
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data["status"], "pendente")
        self.assertEqual(r.data["valor"], 8990)
        self.assertIn("/api/pagamentos/simulador/", r.data["checkout_url"])
        self.assertEqual([e["evento"] for e in self.eventos], ["pagamento.pendente"])
        self.assertEqual(self.eventos[0]["empresa_id"], 1)
        self.assertEqual(self.eventos[0]["email"], "admin@champion.com")

    def test_padrao_nao_contrata(self):
        r = self.criar(cliente(perfil="padrao"))
        self.assertEqual(r.status_code, 403)

    def test_sem_token(self):
        self.assertEqual(APIClient().get("/api/pagamentos/cobrancas/").status_code, 401)

    def test_token_assinado_com_outra_chave(self):
        import time

        import jwt
        falso = jwt.encode({"token_type": "access", "user_id": 1, "empresa_id": 1, "perfil": "administrador",
                            "exp": int(time.time()) + 600, "jti": "x"}, "chave-de-um-atacante", algorithm="HS256")
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {falso}")
        self.assertEqual(c.get("/api/pagamentos/cobrancas/").status_code, 401)

    def test_empresa_so_ve_as_proprias_cobrancas(self):
        self.criar()
        self.assertEqual(cliente().get("/api/pagamentos/cobrancas/").data["count"], 1)
        self.assertEqual(cliente(empresa_id=2).get("/api/pagamentos/cobrancas/").data["count"], 0)

    def test_cada_status_publica_um_evento(self):
        cid = self.criar().data["id"]
        c = Cobranca.objects.get(pk=cid)
        with self.captureOnCommitCallbacks(execute=True):
            services.mudar_status(c, "pago", "teste")
        with self.captureOnCommitCallbacks(execute=True):
            services.mudar_status(c, "reembolsado", "teste")
        self.assertEqual([e["evento"] for e in self.eventos],
                         ["pagamento.pendente", "pagamento.pago", "pagamento.reembolsado"])
        self.assertEqual(c.historico.count(), 3)

    def test_transicao_invalida(self):
        c = Cobranca.objects.get(pk=self.criar().data["id"])
        services.mudar_status(c, "cancelado", "teste")
        with self.assertRaises(services.CobrancaError):
            services.mudar_status(c, "pago", "teste")

    def test_simulador_paga(self):
        cid = self.criar().data["id"]
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"/api/pagamentos/simulador/{cid}/", {"acao": "pagar"})
        self.assertEqual(Cobranca.objects.get(pk=cid).status, "pago")
        self.assertEqual(self.eventos[-1]["evento"], "pagamento.pago")
        self.assertContains(self.client.get(f"/api/pagamentos/simulador/{cid}/"), "Reembolsar")

    @override_settings(WEBHOOK_SECRET="segredo")
    def test_webhook_abacatepay_e_idempotente(self):
        cid = self.criar().data["id"]
        payload = {"id": "evt_1", "event": "billing.paid",
                   "data": {"billing": {"id": "bill_1", "metadata": {"cobranca_id": cid}}}}
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.post("/api/pagamentos/webhook/abacatepay/?secret=segredo", payload,
                                 content_type="application/json")
        self.assertEqual(r.json()["status"], "updated")
        r = self.client.post("/api/pagamentos/webhook/abacatepay/?secret=segredo", payload,
                             content_type="application/json")
        self.assertEqual(r.json()["status"], "ignored")
        self.assertEqual([e["evento"] for e in self.eventos], ["pagamento.pendente", "pagamento.pago"])

    def test_webhook_secret_invalido(self):
        r = self.client.post("/api/pagamentos/webhook/abacatepay/?secret=x", {}, content_type="application/json")
        self.assertEqual(r.status_code, 401)

    def test_planos_publico(self):
        r = APIClient().get("/api/pagamentos/planos/")
        self.assertEqual({p["plano"] for p in r.data}, {"prata", "ouro"})


class EmailTests(TestCase):
    def test_um_email_por_status(self):
        base = {"cobranca_id": "abc", "plano": "ouro", "valor": 11990, "email": "cliente@x.com",
                "nome_cliente": "João", "empresa_nome": "Champion", "checkout_url": "http://pagar"}
        for status in ["pendente", "pago", "expirado", "cancelado", "reembolsado"]:
            enviar_email_status({**base, "status": status, "evento": f"pagamento.{status}"})
        self.assertEqual(len(mail.outbox), 5)
        assuntos = [m.subject for m in mail.outbox]
        self.assertIn("aguardando pagamento", assuntos[0])
        self.assertIn("confirmado", assuntos[1])
        self.assertIn("expirou", assuntos[2])
        self.assertIn("cancelado", assuntos[3])
        self.assertIn("Reembolso", assuntos[4])
        self.assertIn("R$ 119,90", mail.outbox[1].body)
        self.assertEqual(mail.outbox[0].to, ["cliente@x.com"])


class MensageriaTests(TestCase):
    def test_publica_na_exchange_e_chega_na_fila_de_email(self):
        """Usa o transporte em memória do kombu: mesma API do RabbitMQ."""
        evento = {"evento": "pagamento.pago", "status": "pago", "cobranca_id": "abc"}
        with Connection("memory://") as conn:
            mensageria.FILA_EMAIL(conn.default_channel).declare()
            mensageria.publicar(evento, conexao_url="memory://")
            recebidos = []
            with conn.Consumer(mensageria.FILA_EMAIL, callbacks=[lambda b, m: (recebidos.append(b), m.ack())],
                               accept=["json"]):
                conn.drain_events(timeout=2)
        self.assertEqual(recebidos, [evento])
