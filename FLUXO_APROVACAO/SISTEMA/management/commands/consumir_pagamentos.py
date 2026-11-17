"""
Consumidor da fila "flow.assinaturas" (RabbitMQ).

Escuta a exchange "pagamentos" do microserviço de pagamentos:
    pagamento.pago         -> ativa o plano da empresa por 30 dias
    pagamento.reembolsado  -> cancela a assinatura

    python manage.py consumir_pagamentos
"""
import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from kombu import Connection, Exchange, Queue, binding
from kombu.mixins import ConsumerMixin

from SISTEMA.assinaturas import aplicar_evento_pagamento

logger = logging.getLogger("SISTEMA")

EXCHANGE = Exchange("pagamentos", type="topic", durable=True)
FILA = Queue(
    "flow.assinaturas",
    exchange=EXCHANGE,
    bindings=[binding(EXCHANGE, routing_key="pagamento.pago"),
              binding(EXCHANGE, routing_key="pagamento.reembolsado")],
    durable=True,
)


class Consumidor(ConsumerMixin):
    def __init__(self, connection, stdout):
        self.connection = connection
        self.stdout = stdout

    def get_consumers(self, Consumer, channel):
        return [Consumer(queues=[FILA], callbacks=[self.ao_receber], accept=["json"])]

    def ao_receber(self, evento, message):
        try:
            resultado = aplicar_evento_pagamento(evento)
            self.stdout.write(f"[assinaturas] {evento.get('evento')} cobrança {evento.get('cobranca_id')}: {resultado}")
            message.ack()
        except Exception:
            logger.exception("Erro ao processar evento de pagamento; mensagem volta para a fila")
            message.requeue()


class Command(BaseCommand):
    help = "Consome eventos de pagamento (RabbitMQ) e atualiza as assinaturas das empresas."

    def handle(self, *args, **opts):
        self.stdout.write("Ouvindo a fila 'flow.assinaturas' (pagamento.pago, pagamento.reembolsado)...")
        with Connection(settings.RABBITMQ_URL) as conn:
            Consumidor(conn, self.stdout).run()
