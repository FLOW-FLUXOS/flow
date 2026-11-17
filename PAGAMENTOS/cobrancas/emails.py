"""E-mail enviado para cada status de pagamento (usado pelo consumidor da fila pagamentos.email)."""
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.dateparse import parse_datetime

NOMES_PLANO = {"prata": "Prata", "ouro": "Ouro"}


def _valor(centavos):
    return f"R$ {centavos / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def montar_email(evento: dict) -> tuple[str, str]:
    plano = NOMES_PLANO.get(evento["plano"], evento["plano"].title())
    nome = evento.get("nome_cliente") or "cliente"
    valor = _valor(evento["valor"])
    status = evento["status"]

    if status == "pendente":
        assunto = f"FLOW — Pedido do Plano {plano} aguardando pagamento"
        corpo = (f"Olá, {nome}!\n\nRecebemos o pedido do Plano {plano} ({valor}) para a empresa "
                 f"{evento.get('empresa_nome', '')}.\n\nPara concluir, pague pelo link:\n{evento.get('checkout_url', '')}\n")
    elif status == "pago":
        ocorrido = parse_datetime(evento.get("ocorrido_em", "")) or timezone.now()
        validade = (timezone.localtime(ocorrido) + timedelta(days=30)).strftime("%d/%m/%Y")
        assunto = f"FLOW — Pagamento confirmado: Plano {plano} ativo"
        corpo = (f"Olá, {nome}!\n\nConfirmamos o pagamento de {valor}. O Plano {plano} da empresa "
                 f"{evento.get('empresa_nome', '')} está ativo até {validade}.\n\nObrigado por usar o FLOW!\n")
    elif status == "expirado":
        assunto = f"FLOW — O link de pagamento do Plano {plano} expirou"
        corpo = (f"Olá, {nome}!\n\nO prazo para pagar o Plano {plano} ({valor}) terminou e nenhuma "
                 f"cobrança foi feita. Se ainda quiser assinar, gere um novo pagamento na tela de Planos.\n")
    elif status == "cancelado":
        assunto = f"FLOW — Pagamento do Plano {plano} cancelado"
        corpo = (f"Olá, {nome}!\n\nO pedido do Plano {plano} ({valor}) foi cancelado. "
                 f"Nenhum valor foi cobrado.\n")
    elif status == "reembolsado":
        assunto = f"FLOW — Reembolso do Plano {plano}"
        corpo = (f"Olá, {nome}!\n\nO valor de {valor} referente ao Plano {plano} foi reembolsado. "
                 f"A empresa voltou para o plano Freemium.\n")
    else:
        assunto = f"FLOW — Atualização do pagamento ({status})"
        corpo = f"Olá, {nome}!\n\nO pagamento do Plano {plano} agora está com status: {status}.\n"

    corpo += f"\nCódigo da cobrança: {evento['cobranca_id']}\n— Equipe FLOW"
    return assunto, corpo


def enviar_email_status(evento: dict):
    assunto, corpo = montar_email(evento)
    send_mail(assunto, corpo, settings.DEFAULT_FROM_EMAIL, [evento["email"]], fail_silently=False)
