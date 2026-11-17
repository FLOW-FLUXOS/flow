"""
Consumidor da fila "pagamentos.email" (RabbitMQ).
Para cada evento pagamento.<status>, envia um e-mail ao cliente.

    python manage.py consumir_emails
"""
import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from kombu import Connection
from kombu.mixins import ConsumerMixin

from cobrancas.emails import enviar_email_status
from cobrancas.mensageria import FILA_EMAIL

logger = logging.getLogger("cobrancas")


class ConsumidorEmails(ConsumerMixin):
    def __init__(self, connection, stdout):
        self.connection = connection
        self.stdout = stdout

    def get_consumers(self, Consumer, channel):
        return [Consumer(queues=[FILA_EMAIL], callbacks=[self.ao_receber], accept=["json"], prefetch_count=10)]

    def ao_receber(self, evento, message):
        try:
            enviar_email_status(evento)
            self.stdout.write(f"[e-mail] {evento['evento']} -> {evento['email']} (cobrança {evento['cobranca_id']})")
            message.ack()
        except Exception:
            logger.exception("Falha ao enviar e-mail do evento %s; mensagem volta para a fila", evento.get("evento"))
            message.requeue()


class Command(BaseCommand):
    help = "Consome os eventos de pagamento e envia um e-mail para cada status."

    def handle(self, *args, **opts):
        self.stdout.write(f"Ouvindo a fila '{FILA_EMAIL.name}' (routing key '{FILA_EMAIL.routing_key}')...")
        with Connection(settings.RABBITMQ_URL) as conn:
            ConsumidorEmails(conn, self.stdout).run()
