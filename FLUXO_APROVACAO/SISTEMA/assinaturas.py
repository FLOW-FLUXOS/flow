"""
Reação da API principal aos eventos de pagamento (vindos do RabbitMQ).
"""
import logging

from django.db import transaction
from django.utils import timezone

from .models import Assinatura, Empresa, Usuario

logger = logging.getLogger(__name__)


@transaction.atomic
def aplicar_evento_pagamento(evento: dict) -> str:
    status = evento.get("status")
    cobranca_id = str(evento.get("cobranca_id") or "")

    if status == "pago":
        if Assinatura.objects.filter(cobranca_id=cobranca_id).exists():
            return "ignorado: já processado"
        empresa = Empresa.objects.filter(pk=evento.get("empresa_id")).first()
        if not empresa:
            return "ignorado: empresa não encontrada"
        hoje = timezone.localdate()
        empresa.assinaturas.filter(status="ativo").update(status="inativo")
        Assinatura.objects.create(
            empresa=empresa,
            usuario=Usuario.objects.filter(pk=evento.get("usuario_id"), empresa=empresa).first(),
            plano=evento["plano"], status="ativo", cobranca_id=cobranca_id,
            data_inicio=hoje, data_fim=Assinatura.calcular_data_fim(hoje),
        )
        return f"plano {evento['plano']} ativado para {empresa.nome}"

    if status == "reembolsado":
        total = Assinatura.objects.filter(cobranca_id=cobranca_id, status="ativo").update(status="cancelado")
        return "assinatura cancelada" if total else "ignorado: assinatura não encontrada"

    return f"ignorado: status {status}"
