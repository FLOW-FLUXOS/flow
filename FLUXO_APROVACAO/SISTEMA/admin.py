"""Django Admin — painel do dono da plataforma (superusuário), enxerga todas as empresas."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    AcaoFluxo,
    Assinatura,
    DispositivoPush,
    Empresa,
    EtapaFluxo,
    EtapaInstancia,
    FluxoInstancia,
    FluxoPadrao,
    MovimentacaoFluxo,
    Notificacao,
    Setor,
    Usuario,
)


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ("nome", "cnpj", "plano_atual", "total_usuarios", "ativo", "criado_em")
    list_filter = ("ativo",)
    search_fields = ("nome", "cnpj")


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ("username", "email", "empresa", "setor", "perfil", "is_active")
    list_filter = ("empresa", "perfil", "is_active")
    fieldsets = UserAdmin.fieldsets + (("FLOW", {"fields": ("empresa", "setor", "perfil")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("FLOW", {"fields": ("empresa", "setor", "perfil")}),)


@admin.register(Setor)
class SetorAdmin(admin.ModelAdmin):
    list_display = ("nome", "empresa")
    list_filter = ("empresa",)


class EtapaFluxoInline(admin.TabularInline):
    model = EtapaFluxo
    extra = 0


@admin.register(FluxoPadrao)
class FluxoPadraoAdmin(admin.ModelAdmin):
    list_display = ("nome", "empresa", "criado_por", "criado_em")
    list_filter = ("empresa",)
    inlines = [EtapaFluxoInline]


class EtapaInstanciaInline(admin.TabularInline):
    model = EtapaInstancia
    extra = 0


@admin.register(FluxoInstancia)
class FluxoInstanciaAdmin(admin.ModelAdmin):
    list_display = ("nome", "empresa", "modelo", "finalizado", "criado_em")
    list_filter = ("empresa", "finalizado")
    inlines = [EtapaInstanciaInline]


@admin.register(MovimentacaoFluxo)
class MovimentacaoAdmin(admin.ModelAdmin):
    list_display = ("fluxo_instancia", "etapa", "acao", "usuario", "data_acao")


@admin.register(Assinatura)
class AssinaturaAdmin(admin.ModelAdmin):
    list_display = ("empresa", "plano", "status", "data_inicio", "data_fim", "cobranca_id")
    list_filter = ("plano", "status")


@admin.register(Notificacao)
class NotificacaoAdmin(admin.ModelAdmin):
    list_display = ("usuario", "tipo", "titulo", "lida", "criado_em")
    list_filter = ("tipo", "lida")


admin.site.register([AcaoFluxo, DispositivoPush])
admin.site.site_header = "FLOW — Administração da Plataforma"
