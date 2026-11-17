"""
Mensageria do serviço de Pagamentos (RabbitMQ via kombu).

    Exchange:  "pagamentos"  (tipo topic, durável)
    Routing:   pagamento.pendente | pagamento.pago | pagamento.expirado
               pagamento.cancelado | pagamento.reembolsado

Quem escuta (cada um com a sua fila):
    pagamentos.email     <- pagamento.*                       (este serviço: envia e-mail)
    flow.assinaturas     <- pagamento.pago, pagamento.reembolsado   (API principal: ativa o plano)
"""
import logging

from django.conf import settings
from kombu import Connection, Exchange, Queue

logger = logging.getLogger(__name__)

exchange_pagamentos = Exchange(settings.EXCHANGE_PAGAMENTOS, type="topic", durable=True)

FILA_EMAIL = Queue(
    "pagamentos.email", exchange=exchange_pagamentos, routing_key="pagamento.*", durable=True
)


def routing_key(status: str) -> str:
    return f"pagamento.{status}"


def publicar(evento: dict, conexao_url: str | None = None):
    """Publica o evento na exchange. A mensagem é persistente (sobrevive a restart do RabbitMQ)."""
    url = conexao_url or settings.RABBITMQ_URL
    chave = routing_key(evento["status"])
    with Connection(url) as conn:
        producer = conn.Producer(serializer="json")
        producer.publish(
            evento,
            exchange=exchange_pagamentos,
            routing_key=chave,
            declare=[exchange_pagamentos, FILA_EMAIL],
            delivery_mode=2,
            retry=True,
            retry_policy={"max_retries": 3, "interval_start": 1, "interval_step": 2},
        )
    logger.info("Evento publicado: %s (cobrança %s)", chave, evento["cobranca_id"])
