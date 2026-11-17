"""
Regras de negócio do FLOW.

Tudo que altera fluxo passa por aqui — tanto a API (mobile) quanto o
backoffice web chamam estas funções, então a regra é uma só.
"""
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .eventos import publicar_evento_fluxo
from .models import (
    AcaoFluxo,
    EtapaInstancia,
    FluxoInstancia,
    FluxoPadrao,
    MovimentacaoFluxo,
    Usuario,
)


class RegraNegocioError(Exception):
    """Erro de regra de negócio (vira 400 na API / mensagem no web)."""


class PermissaoNegadaError(RegraNegocioError):
    """Usuário não tem permissão para a ação (vira 403 na API)."""


# ----------------------------------------------------------
# Consultas / permissões
# ----------------------------------------------------------
def etapa_atual(instancia: FluxoInstancia):
    return instancia.etapas.filter(concluida=False).order_by("ordem_etapa").first()


def pode_aprovar(usuario: Usuario, etapa: EtapaInstancia) -> bool:
    """
    Quem pode aprovar (avançar/retornar) a etapa atual de um fluxo:
      - precisa ser da mesma empresa do fluxo;
      - administradores da empresa podem atuar em qualquer etapa;
      - usuário padrão: só em etapas com perfil_aprovador "padrao" e
        do seu setor (ou etapas sem setor definido).
    """
    if etapa is None or not usuario.is_authenticated:
        return False
    instancia = etapa.fluxo_instancia
    if instancia.finalizado or etapa.concluida:
        return False
    if usuario.empresa_id != instancia.empresa_id:
        return False
    atual = etapa_atual(instancia)
    if atual is None or atual.pk != etapa.pk:
        return False
    if usuario.is_admin_empresa:
        return True
    if etapa.perfil_aprovador == "administrador":
        return False
    return etapa.setor_id is None or etapa.setor_id == usuario.setor_id


def aprovadores_da_etapa(etapa: EtapaInstancia):
    """Usuários que devem ser avisados de que a etapa está esperando por eles."""
    empresa_id = etapa.fluxo_instancia.empresa_id
    base = Usuario.objects.filter(empresa_id=empresa_id, is_active=True)

    if etapa.perfil_aprovador == "administrador":
        qs = base.filter(perfil="administrador")
        if etapa.setor_id:
            no_setor = qs.filter(setor_id=etapa.setor_id)
            if no_setor.exists():
                qs = no_setor
        return qs

    qs = base.filter(perfil="padrao")
    if etapa.setor_id:
        qs = qs.filter(setor_id=etapa.setor_id)
    if not qs.exists():
        # ninguém do setor cadastrado -> admins recebem para não travar o fluxo
        qs = base.filter(perfil="administrador")
    return qs


def instancias_pendentes_para(usuario: Usuario):
    """Fluxos em andamento cuja etapa atual o usuário pode aprovar."""
    qs = FluxoInstancia.objects.filter(empresa_id=usuario.empresa_id, finalizado=False)
    ids = []
    for instancia in qs.prefetch_related("etapas"):
        atual = next((e for e in sorted(instancia.etapas.all(), key=lambda e: e.ordem_etapa) if not e.concluida), None)
        if atual and pode_aprovar(usuario, atual):
            ids.append(instancia.id)
    return FluxoInstancia.objects.filter(id__in=ids)


def _acao(nome):
    acao, _ = AcaoFluxo.objects.get_or_create(nome=nome)
    return acao


# ----------------------------------------------------------
# Comandos
# ----------------------------------------------------------
@transaction.atomic
def criar_instancia(usuario: Usuario, modelo: FluxoPadrao, nome: str, comentario: str = "") -> FluxoInstancia:
    if modelo.empresa_id != usuario.empresa_id:
        raise PermissaoNegadaError("Modelo de fluxo não pertence à sua empresa.")
    etapas_modelo = list(modelo.etapas.order_by("ordem_etapa"))
    if not etapas_modelo:
        raise RegraNegocioError("O modelo de fluxo não possui etapas.")
    nome = (nome or "").strip()
    if not nome:
        raise RegraNegocioError("Informe o nome do fluxo.")

    instancia = FluxoInstancia.objects.create(
        empresa_id=usuario.empresa_id, modelo=modelo, nome=nome, criado_por=usuario
    )
    agora = timezone.now()
    for i, etapa in enumerate(etapas_modelo, start=1):
        EtapaInstancia.objects.create(
            fluxo_instancia=instancia,
            ordem_etapa=i,
            nome=etapa.nome,
            setor=etapa.setor,
            perfil_aprovador=etapa.perfil_aprovador,
            criado_em=agora,
        )

    primeira = etapa_atual(instancia)
    MovimentacaoFluxo.objects.create(
        fluxo_instancia=instancia, etapa=primeira, usuario=usuario,
        acao=_acao("Criação"), comentario=comentario or None,
    )
    publicar_evento_fluxo("criado", instancia.id, usuario.id, primeira.id)
    return instancia


def _travar(instancia: FluxoInstancia) -> FluxoInstancia:
    return FluxoInstancia.objects.select_for_update().get(pk=instancia.pk)


@transaction.atomic
def avancar(usuario: Usuario, instancia: FluxoInstancia, comentario: str = "", etapa_id=None) -> FluxoInstancia:
    """Aprova a etapa atual e passa para a próxima (ou finaliza)."""
    instancia = _travar(instancia)
    if instancia.finalizado:
        raise RegraNegocioError("Este fluxo já está finalizado.")
    etapa = etapa_atual(instancia)
    if etapa is None:
        raise RegraNegocioError("Fluxo sem etapas pendentes.")
    if etapa_id is not None and int(etapa_id) != etapa.id:
        raise RegraNegocioError("Só é possível movimentar a etapa atual do fluxo.")
    if not pode_aprovar(usuario, etapa):
        raise PermissaoNegadaError("Você não tem permissão para aprovar esta etapa.")

    etapa.concluida = True
    etapa.save(update_fields=["concluida"])
    MovimentacaoFluxo.objects.create(
        fluxo_instancia=instancia, etapa=etapa, usuario=usuario,
        acao=_acao("Avançar"), comentario=(comentario or "").strip() or None,
    )

    proxima = etapa_atual(instancia)
    if proxima is None:
        instancia.finalizado = True
        instancia.save(update_fields=["finalizado", "atualizado_em"])
        publicar_evento_fluxo("finalizado", instancia.id, usuario.id)
    else:
        instancia.save(update_fields=["atualizado_em"])
        publicar_evento_fluxo("avancado", instancia.id, usuario.id, proxima.id)
    return instancia


@transaction.atomic
def retornar(usuario: Usuario, instancia: FluxoInstancia, comentario: str = "", etapa_id=None) -> FluxoInstancia:
    """Devolve o fluxo para a etapa anterior."""
    instancia = _travar(instancia)
    if instancia.finalizado:
        raise RegraNegocioError("Este fluxo já está finalizado.")
    etapa = etapa_atual(instancia)
    if etapa is None:
        raise RegraNegocioError("Fluxo sem etapas pendentes.")
    if etapa_id is not None and int(etapa_id) != etapa.id:
        raise RegraNegocioError("Só é possível movimentar a etapa atual do fluxo.")
    if not pode_aprovar(usuario, etapa):
        raise PermissaoNegadaError("Você não tem permissão para movimentar esta etapa.")

    anterior = instancia.etapas.filter(ordem_etapa__lt=etapa.ordem_etapa).order_by("-ordem_etapa").first()
    if anterior is None:
        raise RegraNegocioError("Não é possível retornar: esta é a primeira etapa.")

    anterior.concluida = False
    anterior.save(update_fields=["concluida"])
    instancia.save(update_fields=["atualizado_em"])
    MovimentacaoFluxo.objects.create(
        fluxo_instancia=instancia, etapa=anterior, usuario=usuario,
        acao=_acao("Retornar"), comentario=(comentario or "").strip() or None,
    )
    publicar_evento_fluxo("retornado", instancia.id, usuario.id, anterior.id)
    return instancia


def validar_limite_usuarios(empresa):
    if not empresa.pode_adicionar_usuario():
        raise RegraNegocioError(
            f"O plano {empresa.plano_atual.title()} permite até {empresa.limite_usuarios} "
            f"usuário(s). Faça upgrade para adicionar mais."
        )


def filtro_busca_instancias(qs, termo):
    if termo:
        qs = qs.filter(Q(nome__icontains=termo) | Q(modelo__nome__icontains=termo))
    return qs
