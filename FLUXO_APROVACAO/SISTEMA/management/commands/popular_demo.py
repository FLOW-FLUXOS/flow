"""
Cria uma empresa de demonstração com usuários, setores e um modelo de fluxo.

    python manage.py popular_demo
    docker compose exec web python manage.py popular_demo

Usuários criados (senha: Flow@2026):
    demo.admin       administrador
    demo.engenharia  setor Engenharia
    demo.financeiro  setor Financeiro
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from SISTEMA.models import Assinatura, Empresa, EtapaFluxo, FluxoPadrao, Setor, Usuario

SENHA = "Flow@2026"


class Command(BaseCommand):
    help = "Popula uma empresa de demonstração para testar o app."

    @transaction.atomic
    def handle(self, *args, **opts):
        empresa, criada = Empresa.objects.get_or_create(nome="FLOW Demo")
        if not criada:
            self.stdout.write(self.style.WARNING("Empresa 'FLOW Demo' já existe — nada a fazer."))
            return

        Assinatura.objects.create(empresa=empresa, plano="ouro", status="ativo",
                                  data_inicio=timezone.localdate())
        eng = Setor.objects.create(empresa=empresa, nome="Engenharia")
        fin = Setor.objects.create(empresa=empresa, nome="Financeiro")

        def user(username, perfil="padrao", setor=None, nome=""):
            u = Usuario(username=username, email=f"{username}@flow.demo", empresa=empresa,
                        perfil=perfil, setor=setor, first_name=nome)
            u.set_password(SENHA)
            u.save()
            return u

        admin = user("demo.admin", "administrador", nome="Admin")
        user("demo.engenharia", setor=eng, nome="Engenharia")
        user("demo.financeiro", setor=fin, nome="Financeiro")

        modelo = FluxoPadrao.objects.create(empresa=empresa, nome="Solicitação de compra",
                                            descricao="Compra de material", criado_por=admin)
        EtapaFluxo.objects.create(fluxo=modelo, ordem_etapa=1, nome="Análise técnica", setor=eng)
        EtapaFluxo.objects.create(fluxo=modelo, ordem_etapa=2, nome="Aprovação financeira", setor=fin)
        EtapaFluxo.objects.create(fluxo=modelo, ordem_etapa=3, nome="Diretoria", perfil_aprovador="administrador")

        self.stdout.write(self.style.SUCCESS(
            f"Empresa demo criada. Usuários: demo.admin, demo.engenharia, demo.financeiro (senha {SENHA})"))
