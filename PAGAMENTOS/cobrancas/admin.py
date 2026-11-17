from django.contrib import admin

from .models import Cobranca, HistoricoStatus


class HistoricoInline(admin.TabularInline):
    model = HistoricoStatus
    extra = 0
    readonly_fields = ("status", "origem", "event_id", "criado_em")


@admin.register(Cobranca)
class CobrancaAdmin(admin.ModelAdmin):
    list_display = ("id", "empresa_nome", "plano", "valor_formatado", "status", "gateway", "criado_em")
    list_filter = ("status", "plano", "gateway")
    search_fields = ("empresa_nome", "email", "billing_id")
    inlines = [HistoricoInline]
