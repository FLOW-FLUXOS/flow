import uuid

from django.db import models
from django.utils import timezone

PLANOS = {
    # plano: (nome, preço em centavos)
    "prata": ("Plano Prata", 8990),
    "ouro": ("Plano Ouro", 11990),
}


class Cobranca(models.Model):
    """Uma tentativa de pagamento de plano feita por uma empresa."""

    PENDENTE, PAGO, EXPIRADO, CANCELADO, REEMBOLSADO = "pendente", "pago", "expirado", "cancelado", "reembolsado"
    STATUS_CHOICES = [
        (PENDENTE, "Aguardando pagamento"),
        (PAGO, "Pago"),
        (EXPIRADO, "Expirado"),
        (CANCELADO, "Cancelado"),
        (REEMBOLSADO, "Reembolsado"),
    ]
    # para onde cada status pode ir
    TRANSICOES = {
        PENDENTE: {PAGO, EXPIRADO, CANCELADO},
        PAGO: {REEMBOLSADO},
        EXPIRADO: set(),
        CANCELADO: set(),
        REEMBOLSADO: set(),
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # dados vindos do token da API principal (este serviço não tem tabela de usuários)
    empresa_id = models.BigIntegerField(db_index=True)
    empresa_nome = models.CharField(max_length=200, blank=True)
    usuario_id = models.BigIntegerField()
    nome_cliente = models.CharField(max_length=200, blank=True)
    email = models.EmailField()

    plano = models.CharField(max_length=20, choices=[(k, v[0]) for k, v in PLANOS.items()])
    valor = models.PositiveIntegerField(help_text="Em centavos")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDENTE, db_index=True)
    gateway = models.CharField(max_length=20, default="simulador")  # simulador | abacatepay
    billing_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    checkout_url = models.URLField(max_length=500, blank=True)
    criado_em = models.DateTimeField(default=timezone.now)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cobrancas"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.empresa_nome} - {self.plano} ({self.status})"

    @property
    def valor_formatado(self):
        return f"R$ {self.valor / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class HistoricoStatus(models.Model):
    """Rastreabilidade: cada mudança de status da cobrança."""
    cobranca = models.ForeignKey(Cobranca, on_delete=models.CASCADE, related_name="historico")
    status = models.CharField(max_length=20, choices=Cobranca.STATUS_CHOICES)
    origem = models.CharField(max_length=30)  # checkout | webhook | simulador
    event_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    payload = models.JSONField(null=True, blank=True)
    criado_em = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "cobrancas_historico"
        ordering = ["criado_em"]
