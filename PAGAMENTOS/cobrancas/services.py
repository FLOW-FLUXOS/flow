"""
Regras de negócio das cobranças.
Toda mudança de status passa por mudar_status(), que grava o histórico
e publica o evento no RabbitMQ depois do commit.
"""
import logging

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from . import mensageria
from .models import PLANOS, Cobranca, HistoricoStatus

logger = logging.getLogger(__name__)

ABACATE_URL = "https://api.abacatepay.com/v1/billing/create"

# eventos do AbacatePay -> nosso status
EVENTOS_ABACATEPAY = {
    "billing.paid": Cobranca.PAGO,
    "billing.expired": Cobranca.EXPIRADO,
    "billing.cancelled": Cobranca.CANCELADO,
    "billing.canceled": Cobranca.CANCELADO,
    "billing.refunded": Cobranca.REEMBOLSADO,
}


class CobrancaError(Exception):
    pass


def montar_evento(c: Cobranca) -> dict:
    return {
        "evento": mensageria.routing_key(c.status),
        "cobranca_id": str(c.id),
        "status": c.status,
        "plano": c.plano,
        "valor": c.valor,
        "empresa_id": c.empresa_id,
        "empresa_nome": c.empresa_nome,
        "usuario_id": c.usuario_id,
        "nome_cliente": c.nome_cliente,
        "email": c.email,
        "checkout_url": c.checkout_url,
        "ocorrido_em": timezone.now().isoformat(),
    }


def _publicar_apos_commit(cobranca: Cobranca):
    evento = montar_evento(cobranca)

    def _enviar():
        try:
            mensageria.publicar(evento)
        except Exception:
            # o pagamento já está gravado; só a notificação falhou
            logger.exception("Falha ao publicar %s no RabbitMQ", evento["evento"])

    transaction.on_commit(_enviar)


@transaction.atomic
def criar_cobranca(token, plano: str, return_url: str | None = None, cnpj: str = "", telefone: str = "") -> Cobranca:
    """Cria a cobrança para a empresa do usuário do token e gera o link de pagamento."""
    if plano not in PLANOS:
        raise CobrancaError("Plano inválido. Use 'prata' ou 'ouro' (Diamante é sob consulta).")
    nome_plano, preco = PLANOS[plano]

    c = Cobranca.objects.create(
        empresa_id=token["empresa_id"],
        empresa_nome=token.get("empresa_nome", ""),
        usuario_id=token["user_id"],
        nome_cliente=token.get("nome", ""),
        email=token.get("email") or "sem-email@flow.local",
        plano=plano,
        valor=preco,
        gateway="simulador" if settings.SIMULADOR_ATIVO else "abacatepay",
    )

    if settings.SIMULADOR_ATIVO:
        c.checkout_url = f"{settings.PUBLIC_URL}/api/pagamentos/simulador/{c.id}/"
    else:
        c.billing_id, c.checkout_url = _criar_no_abacatepay(c, nome_plano, return_url, cnpj, telefone)
    c.save(update_fields=["checkout_url", "billing_id"])

    HistoricoStatus.objects.create(cobranca=c, status=c.status, origem="checkout")
    _publicar_apos_commit(c)
    return c


def _criar_no_abacatepay(c: Cobranca, nome_plano, return_url, cnpj, telefone):
    payload = {
        "frequency": "ONE_TIME",
        "methods": ["PIX"],
        "products": [{
            "externalId": str(c.id),
            "name": nome_plano,
            "description": f"{nome_plano} - 30 dias",
            "quantity": 1,
            "price": c.valor,
        }],
        "returnUrl": return_url or settings.PUBLIC_URL,
        "completionUrl": return_url or settings.PUBLIC_URL,
        "allowCoupons": False,
        "metadata": {"cobranca_id": str(c.id), "empresa_id": str(c.empresa_id)},
    }
    if cnpj and telefone:
        payload["customer"] = {"name": c.empresa_nome or c.nome_cliente, "cellphone": telefone,
                               "email": c.email, "taxId": cnpj}
    try:
        resp = requests.post(ABACATE_URL, json=payload, timeout=10,
                             headers={"Authorization": f"Bearer {settings.ABACATEPAY_API_KEY}"})
        data = resp.json()
    except Exception as exc:
        raise CobrancaError(f"Não foi possível falar com o AbacatePay: {exc}") from exc
    info = data.get("data") or {}
    if not info.get("url"):
        raise CobrancaError(f"Erro do AbacatePay: {data.get('error') or data}")
    return info.get("id"), info["url"]


@transaction.atomic
def mudar_status(cobranca: Cobranca, novo: str, origem: str, event_id=None, payload=None) -> bool:
    """Muda o status (respeitando as transições). Devolve False se nada mudou."""
    cobranca = Cobranca.objects.select_for_update().get(pk=cobranca.pk)
    if event_id and HistoricoStatus.objects.filter(event_id=event_id).exists():
        return False  # webhook repetido
    if novo == cobranca.status:
        return False
    if novo not in Cobranca.TRANSICOES[cobranca.status]:
        raise CobrancaError(f"Não é possível ir de '{cobranca.status}' para '{novo}'.")

    cobranca.status = novo
    cobranca.save(update_fields=["status", "atualizado_em"])
    HistoricoStatus.objects.create(cobranca=cobranca, status=novo, origem=origem,
                                   event_id=event_id, payload=payload)
    _publicar_apos_commit(cobranca)
    return True


def processar_webhook_abacatepay(payload: dict) -> dict:
    novo = EVENTOS_ABACATEPAY.get(payload.get("event"))
    if not novo:
        return {"status": "ignored", "reason": "evento não tratado"}
    billing = (payload.get("data") or {}).get("billing") or {}
    cobranca_id = (billing.get("metadata") or {}).get("cobranca_id")
    if not cobranca_id:
        produtos = billing.get("products") or []
        cobranca_id = produtos[0].get("externalId") if produtos else None

    c = Cobranca.objects.filter(pk=cobranca_id).first() if cobranca_id else None
    if c is None and billing.get("id"):
        c = Cobranca.objects.filter(billing_id=billing["id"]).first()
    if c is None:
        return {"status": "ignored", "reason": "cobrança não encontrada"}

    try:
        mudou = mudar_status(c, novo, "webhook", event_id=payload.get("id"), payload=payload)
    except CobrancaError as e:
        return {"status": "ignored", "reason": str(e)}
    return {"status": "updated" if mudou else "ignored", "cobranca": str(c.id), "novo_status": novo}
