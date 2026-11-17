"""
Publicação de eventos de fluxo no message broker (RabbitMQ via Celery).

Os eventos só são publicados depois do COMMIT da transação, assim o
worker nunca lê um estado que ainda não foi gravado no banco.
"""
import logging

from django.db import transaction

logger = logging.getLogger(__name__)

TIPOS_EVENTO = ("criado", "avancado", "retornado", "finalizado")


def publicar_evento_fluxo(tipo: str, instancia_id: int, usuario_id: int | None = None,
                          etapa_id: int | None = None):
    """etapa_id = etapa atual no momento do evento (None quando o fluxo finalizou)."""
    if tipo not in TIPOS_EVENTO:
        raise ValueError(f"Evento desconhecido: {tipo}")

    def _enviar():
        from .tasks import processar_evento_fluxo

        try:
            processar_evento_fluxo.delay(tipo, instancia_id, usuario_id, etapa_id)
        except Exception:  # broker fora do ar não pode derrubar a aprovação
            logger.exception("Falha ao publicar evento '%s' do fluxo %s no broker", tipo, instancia_id)

    transaction.on_commit(_enviar)
