from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

PERFIL_CHOICES = [("administrador", "Administrador"), ("padrao", "Padrão")]


# ==========================================================
# EMPRESA (TENANT) — cada cliente do SaaS é uma empresa
# ==========================================================
class Empresa(models.Model):
    """Empresa cliente do SaaS. Todos os dados do sistema pertencem a uma empresa."""

    # Quantos usuários cada plano permite (None = ilimitado)
    LIMITE_USUARIOS = {"freemium": 1, "prata": 5, "ouro": 10, "diamante": None}

    nome = models.CharField(max_length=200)
    cnpj = models.CharField(max_length=18, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    telefone = models.CharField(max_length=20, blank=True, null=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "empresas"
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"

    def __str__(self):
        return self.nome

    def assinatura_atual(self):
        """Assinatura ativa e dentro da validade (ou None)."""
        for assinatura in self.assinaturas.filter(status="ativo").order_by("-data_inicio", "-id"):
            if assinatura.is_active():
                return assinatura
        return None

    @property
    def plano_atual(self):
        assinatura = self.assinatura_atual()
        return assinatura.plano if assinatura else "freemium"

    @property
    def limite_usuarios(self):
        return self.LIMITE_USUARIOS.get(self.plano_atual)

    @property
    def total_usuarios(self):
        return self.usuarios.filter(is_active=True).count()

    def pode_adicionar_usuario(self):
        limite = self.limite_usuarios
        return limite is None or self.total_usuarios < limite


# ==========================================================
# ESTRUTURA ORGANIZACIONAL
# ==========================================================
class Setor(models.Model):
    """Setores da empresa (ex: Financeiro, Engenharia)."""
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="setores", null=True)
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True, null=True)
    criado_em = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "setores"
        verbose_name = "Setor"
        verbose_name_plural = "Setores"
        unique_together = ("empresa", "nome")

    def __str__(self):
        return self.nome


class Usuario(AbstractUser):
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="usuarios", null=True, blank=True
    )
    setor = models.ForeignKey("Setor", on_delete=models.SET_NULL, null=True, blank=True)
    perfil = models.CharField(max_length=20, choices=PERFIL_CHOICES, default="padrao")
    criado_em = models.DateTimeField(default=timezone.now)

    groups = models.ManyToManyField('auth.Group', related_name='usuarios_sistema', blank=True)
    user_permissions = models.ManyToManyField('auth.Permission', related_name='usuarios_sistema', blank=True)

    class Meta:
        db_table = "usuarios"
        verbose_name = "Usuário"
        verbose_name_plural = "Usuários"

    @property
    def is_admin_empresa(self):
        return self.perfil == "administrador" or self.is_superuser

    def assinatura_atual(self):
        return self.empresa.assinatura_atual() if self.empresa else None

    def __str__(self):
        return self.username


# ==========================================================
# ASSINATURA / LICENCIAMENTO (por empresa)
# ==========================================================
class Assinatura(models.Model):
    PLANO_CHOICES = [
        ("freemium", "Freemium"),
        ("prata", "Prata"),
        ("ouro", "Ouro"),
        ("diamante", "Diamante"),
    ]
    STATUS_CHOICES = [
        ("ativo", "Ativo"),
        ("inativo", "Inativo"),
        ("cancelado", "Cancelado"),
    ]
    DURACAO_DIAS = 30

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="assinaturas", null=True)
    # quem contratou (histórico)
    usuario = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, related_name="assinaturas", null=True, blank=True
    )
    plano = models.CharField(max_length=20, choices=PLANO_CHOICES)
    data_inicio = models.DateField()
    data_fim = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ativo")
    # id da cobrança no microserviço de pagamentos que gerou esta assinatura
    cobranca_id = models.CharField(max_length=64, unique=True, null=True, blank=True)
    criado_em = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "assinaturas"
        verbose_name = "Assinatura"
        verbose_name_plural = "Assinaturas"

    def __str__(self):
        return f"{self.empresa} - {self.plano} ({self.status})"

    def is_active(self):
        if self.status != "ativo":
            return False
        if not self.data_fim:
            return True
        return self.data_fim >= timezone.localdate()

    @property
    def dias_restantes(self):
        if not self.data_fim:
            return None
        return max((self.data_fim - timezone.localdate()).days, 0)

    def expire(self):
        self.status = "inativo"
        self.save(update_fields=["status"])

    @classmethod
    def calcular_data_fim(cls, inicio):
        return inicio + timedelta(days=cls.DURACAO_DIAS)


# ==========================================================
# FLUXO PADRÃO (MODELO / TEMPLATE)
# ==========================================================
class FluxoPadrao(models.Model):
    """Modelos de fluxo criados pelos administradores."""
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="modelos_fluxo", null=True)
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True, null=True)
    criado_por = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True)
    criado_em = models.DateTimeField(default=timezone.now)
    atualizado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "fluxos_padrao"
        verbose_name = "Fluxo Padrão"
        verbose_name_plural = "Fluxos Padrões"

    def __str__(self):
        return self.nome


class EtapaFluxo(models.Model):
    """Etapas definidas dentro do fluxo padrão."""
    fluxo = models.ForeignKey(FluxoPadrao, on_delete=models.CASCADE, related_name="etapas")
    ordem_etapa = models.PositiveIntegerField()
    nome = models.CharField(max_length=200)
    setor = models.ForeignKey(Setor, on_delete=models.SET_NULL, null=True, blank=True)
    perfil_aprovador = models.CharField(max_length=20, choices=PERFIL_CHOICES, default="padrao")
    criado_em = models.DateTimeField(default=timezone.now)
    atualizado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "etapas_fluxo"
        verbose_name = "Etapa do Fluxo"
        verbose_name_plural = "Etapas do Fluxo"
        unique_together = ("fluxo", "ordem_etapa")
        ordering = ["fluxo", "ordem_etapa"]

    def __str__(self):
        return f"{self.fluxo.nome} - Etapa {self.ordem_etapa}: {self.nome}"


# ==========================================================
# INSTÂNCIAS (FLUXOS REAIS EM EXECUÇÃO)
# ==========================================================
class FluxoInstancia(models.Model):
    """Execução real de um fluxo baseado em um modelo padrão."""
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="instancias", null=True)
    modelo = models.ForeignKey(FluxoPadrao, on_delete=models.CASCADE, related_name="instancias")
    nome = models.CharField(max_length=200)
    criado_por = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True)
    criado_em = models.DateTimeField(default=timezone.now)
    atualizado_em = models.DateTimeField(auto_now=True)
    finalizado = models.BooleanField(default=False)

    class Meta:
        db_table = "fluxos_instancia"
        verbose_name = "Fluxo em Execução"
        verbose_name_plural = "Fluxos em Execução"

    def __str__(self):
        return f"{self.nome} (baseado em {self.modelo.nome})"

    @property
    def etapa_atual(self):
        """Primeira etapa não concluída (None quando finalizado)."""
        return self.etapas.filter(concluida=False).order_by("ordem_etapa").first()


class EtapaInstancia(models.Model):
    """Etapas reais, clonadas do modelo, para controle de status."""
    fluxo_instancia = models.ForeignKey(FluxoInstancia, on_delete=models.CASCADE, related_name="etapas")
    ordem_etapa = models.PositiveIntegerField()
    nome = models.CharField(max_length=200)
    setor = models.ForeignKey(Setor, on_delete=models.SET_NULL, null=True, blank=True)
    perfil_aprovador = models.CharField(max_length=20, choices=PERFIL_CHOICES, default="padrao")
    concluida = models.BooleanField(default=False)
    criado_em = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "etapas_instancia"
        verbose_name = "Etapa da Instância"
        verbose_name_plural = "Etapas da Instância"
        unique_together = ("fluxo_instancia", "ordem_etapa")
        ordering = ["fluxo_instancia", "ordem_etapa"]

    def __str__(self):
        return f"{self.fluxo_instancia.nome} - Etapa {self.ordem_etapa}: {self.nome}"


# ==========================================================
# AÇÕES E MOVIMENTAÇÕES
# ==========================================================
class AcaoFluxo(models.Model):
    """Ações possíveis em uma movimentação (ex.: Criação, Avançar, Retornar)."""
    nome = models.CharField(max_length=50, unique=True)
    descricao = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "acoes_fluxo"
        verbose_name = "Ação de Fluxo"
        verbose_name_plural = "Ações de Fluxo"

    def __str__(self):
        return self.nome


class MovimentacaoFluxo(models.Model):
    """Histórico das ações realizadas dentro de uma instância de fluxo."""
    fluxo_instancia = models.ForeignKey(
        FluxoInstancia,
        on_delete=models.CASCADE,
        related_name="movimentacoes",
        null=True,
        blank=True
    )
    etapa = models.ForeignKey(EtapaInstancia, on_delete=models.SET_NULL, null=True, blank=True)
    usuario = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True)
    acao = models.ForeignKey(AcaoFluxo, on_delete=models.SET_NULL, null=True, blank=True)
    comentario = models.TextField(blank=True, null=True)
    data_acao = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "movimentacoes_fluxo"
        verbose_name = "Movimentação do Fluxo"
        verbose_name_plural = "Movimentações do Fluxo"
        ordering = ["-data_acao"]

    def __str__(self):
        usuario = self.usuario.username if self.usuario else "Sistema"
        return f"{self.fluxo_instancia.nome if self.fluxo_instancia else 'Sem Fluxo'} | {self.etapa.nome if self.etapa else '—'} | {self.acao.nome if self.acao else '—'} por {usuario}"


# ==========================================================
# MENSAGERIA — notificações geradas pelo worker (Celery/RabbitMQ)
# ==========================================================
class Notificacao(models.Model):
    TIPO_CHOICES = [
        ("etapa_pendente", "Etapa aguardando aprovação"),
        ("fluxo_avancado", "Fluxo avançou"),
        ("fluxo_retornado", "Fluxo retornado"),
        ("fluxo_finalizado", "Fluxo finalizado"),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="notificacoes")
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="notificacoes")
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES)
    titulo = models.CharField(max_length=200)
    mensagem = models.TextField()
    fluxo_instancia = models.ForeignKey(
        FluxoInstancia, on_delete=models.CASCADE, related_name="notificacoes", null=True, blank=True
    )
    lida = models.BooleanField(default=False)
    criado_em = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "notificacoes"
        verbose_name = "Notificação"
        verbose_name_plural = "Notificações"
        ordering = ["-criado_em"]
        indexes = [models.Index(fields=["usuario", "lida"])]

    def __str__(self):
        return f"{self.usuario} - {self.titulo}"


class DispositivoPush(models.Model):
    """Token de push (Firebase Cloud Messaging) registrado pelo app Flutter."""
    PLATAFORMA_CHOICES = [("android", "Android"), ("ios", "iOS"), ("web", "Web")]

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="dispositivos")
    token = models.CharField(max_length=512, unique=True)
    plataforma = models.CharField(max_length=10, choices=PLATAFORMA_CHOICES, default="android")
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "dispositivos_push"
        verbose_name = "Dispositivo Push"
        verbose_name_plural = "Dispositivos Push"

    def __str__(self):
        return f"{self.usuario} ({self.plataforma})"
