"""
Migração de dados: os registros que já existiam antes do multi-empresa
são vinculados a uma "Empresa Padrão" (pode ser renomeada depois).
Também garante as ações básicas do fluxo (Criação / Avançar / Retornar).
"""
from django.db import migrations


def popular(apps, schema_editor):
    Empresa = apps.get_model("SISTEMA", "Empresa")
    Usuario = apps.get_model("SISTEMA", "Usuario")
    Setor = apps.get_model("SISTEMA", "Setor")
    FluxoPadrao = apps.get_model("SISTEMA", "FluxoPadrao")
    FluxoInstancia = apps.get_model("SISTEMA", "FluxoInstancia")
    Assinatura = apps.get_model("SISTEMA", "Assinatura")
    Pagamento = apps.get_model("SISTEMA", "Pagamento")
    AcaoFluxo = apps.get_model("SISTEMA", "AcaoFluxo")

    for nome, descricao in [
        ("Criação", "Fluxo criado"),
        ("Avançar", "Etapa aprovada e fluxo avançado"),
        ("Retornar", "Fluxo devolvido para a etapa anterior"),
    ]:
        AcaoFluxo.objects.get_or_create(nome=nome, defaults={"descricao": descricao})

    tem_dados = any(
        m.objects.exists() for m in (Usuario, Setor, FluxoPadrao, FluxoInstancia, Assinatura)
    )
    if not tem_dados:
        return

    empresa, _ = Empresa.objects.get_or_create(nome="Empresa Padrão")

    Usuario.objects.filter(empresa__isnull=True, is_superuser=False).update(empresa=empresa)
    # superusers que já operavam o sistema também ficam na empresa padrão
    Usuario.objects.filter(empresa__isnull=True, is_superuser=True).update(empresa=empresa)
    Setor.objects.filter(empresa__isnull=True).update(empresa=empresa)
    FluxoPadrao.objects.filter(empresa__isnull=True).update(empresa=empresa)
    FluxoInstancia.objects.filter(empresa__isnull=True).update(empresa=empresa)
    Assinatura.objects.filter(empresa__isnull=True).update(empresa=empresa)
    Pagamento.objects.filter(empresa__isnull=True).update(empresa=empresa)


class Migration(migrations.Migration):

    dependencies = [
        ("SISTEMA", "0006_empresa_multitenant_notificacoes"),
    ]

    operations = [
        migrations.RunPython(popular, migrations.RunPython.noop),
    ]
