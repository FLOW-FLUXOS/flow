"""
Aplicação Celery do FLOW.

O Django publica eventos de fluxo no RabbitMQ (message broker) e o worker
consome as filas:
  - fluxo.eventos       -> gera as notificações dos aprovadores/criador
  - notificacoes.push   -> envia push para o celular (Firebase, opcional)

Rodar o worker:  celery -A FLUXO_APROVACAO worker -l info -Q default,fluxo.eventos,notificacoes.push
"""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "FLUXO_APROVACAO.settings")

app = Celery("FLUXO_APROVACAO")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
