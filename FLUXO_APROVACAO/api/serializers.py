from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from SISTEMA import services
from SISTEMA.tokens import adicionar_claims
from SISTEMA.models import (
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


def empresa_do_request(serializer):
    return serializer.context["request"].user.empresa


# ==========================================================
# Empresa / Assinatura
# ==========================================================
class EmpresaSerializer(serializers.ModelSerializer):
    plano_atual = serializers.CharField(read_only=True)
    limite_usuarios = serializers.IntegerField(read_only=True, allow_null=True)
    total_usuarios = serializers.IntegerField(read_only=True)

    class Meta:
        model = Empresa
        fields = ["id", "nome", "cnpj", "email", "telefone", "criado_em",
                  "plano_atual", "limite_usuarios", "total_usuarios"]
        read_only_fields = ["id", "criado_em"]


class AssinaturaSerializer(serializers.ModelSerializer):
    dias_restantes = serializers.IntegerField(read_only=True, allow_null=True)
    ativa = serializers.SerializerMethodField()

    class Meta:
        model = Assinatura
        fields = ["id", "plano", "status", "data_inicio", "data_fim", "dias_restantes", "ativa"]

    def get_ativa(self, obj) -> bool:
        return obj.is_active()


# ==========================================================
# Setores / Usuários
# ==========================================================
class SetorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Setor
        fields = ["id", "nome", "descricao", "criado_em"]
        read_only_fields = ["id", "criado_em"]

    def validate_nome(self, nome):
        qs = Setor.objects.filter(empresa=empresa_do_request(self), nome__iexact=nome)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Já existe um setor com este nome.")
        return nome


class SetorResumoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Setor
        fields = ["id", "nome"]


class UsuarioSerializer(serializers.ModelSerializer):
    setor_detalhe = SetorResumoSerializer(source="setor", read_only=True)
    setor = serializers.PrimaryKeyRelatedField(queryset=Setor.objects.all(), required=False, allow_null=True)
    password = serializers.CharField(write_only=True, required=False, style={"input_type": "password"})

    class Meta:
        model = Usuario
        fields = ["id", "username", "email", "first_name", "last_name", "perfil",
                  "setor", "setor_detalhe", "is_active", "criado_em", "password"]
        read_only_fields = ["id", "criado_em"]

    def validate_setor(self, setor):
        if setor and setor.empresa_id != empresa_do_request(self).id:
            raise serializers.ValidationError("Setor não pertence à sua empresa.")
        return setor

    def validate(self, attrs):
        if not self.instance and not attrs.get("password"):
            raise serializers.ValidationError({"password": "Informe uma senha."})
        if attrs.get("password"):
            validate_password(attrs["password"])
        return attrs

    def create(self, validated_data):
        empresa = empresa_do_request(self)
        try:
            services.validar_limite_usuarios(empresa)
        except services.RegraNegocioError as e:
            raise serializers.ValidationError({"detail": str(e)})
        password = validated_data.pop("password")
        user = Usuario(empresa=empresa, **validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for k, v in validated_data.items():
            setattr(instance, k, v)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class MeSerializer(serializers.ModelSerializer):
    """Dados do usuário logado (o app usa para montar a tela inicial)."""
    setor_detalhe = SetorResumoSerializer(source="setor", read_only=True)
    empresa = EmpresaSerializer(read_only=True)
    is_admin = serializers.BooleanField(source="is_admin_empresa", read_only=True)

    class Meta:
        model = Usuario
        fields = ["id", "username", "email", "first_name", "last_name", "perfil",
                  "is_admin", "setor_detalhe", "empresa"]
        read_only_fields = ["id", "username", "perfil", "is_admin", "setor_detalhe", "empresa"]


class TrocarSenhaSerializer(serializers.Serializer):
    senha_atual = serializers.CharField(write_only=True)
    nova_senha = serializers.CharField(write_only=True)

    def validate_senha_atual(self, valor):
        if not self.context["request"].user.check_password(valor):
            raise serializers.ValidationError("Senha atual incorreta.")
        return valor

    def validate_nova_senha(self, valor):
        validate_password(valor, self.context["request"].user)
        return valor


class RegistroSerializer(serializers.Serializer):
    """Cadastro self-service: cria a empresa + o primeiro administrador (plano Freemium)."""
    empresa_nome = serializers.CharField(max_length=200)
    empresa_cnpj = serializers.CharField(max_length=18, required=False, allow_blank=True)
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_username(self, valor):
        if Usuario.objects.filter(username__iexact=valor).exists():
            raise serializers.ValidationError("Nome de usuário já está em uso.")
        return valor

    def validate_password(self, valor):
        validate_password(valor)
        return valor

    @transaction.atomic
    def create(self, data):
        empresa = Empresa.objects.create(
            nome=data["empresa_nome"], cnpj=data.get("empresa_cnpj") or None, email=data["email"]
        )
        user = Usuario(
            empresa=empresa, username=data["username"], email=data["email"],
            first_name=data.get("first_name", ""), last_name=data.get("last_name", ""),
            perfil="administrador",
        )
        user.set_password(data["password"])
        user.save()
        Assinatura.objects.create(
            empresa=empresa, usuario=user, plano="freemium", status="ativo",
            data_inicio=timezone.localdate(),
        )
        return user


class LoginSerializer(TokenObtainPairSerializer):
    """Login JWT: devolve access/refresh + dados do usuário."""

    @classmethod
    def get_token(cls, user):
        return adicionar_claims(super().get_token(user), user)

    def validate(self, attrs):
        data = super().validate(attrs)
        data["usuario"] = MeSerializer(self.user).data
        return data


# ==========================================================
# Modelos de fluxo
# ==========================================================
class EtapaFluxoSerializer(serializers.ModelSerializer):
    setor_detalhe = SetorResumoSerializer(source="setor", read_only=True)
    setor = serializers.PrimaryKeyRelatedField(queryset=Setor.objects.all(), required=False, allow_null=True)

    class Meta:
        model = EtapaFluxo
        fields = ["id", "ordem_etapa", "nome", "setor", "setor_detalhe", "perfil_aprovador"]
        read_only_fields = ["id", "ordem_etapa"]


class FluxoPadraoSerializer(serializers.ModelSerializer):
    """
    As etapas vão na ordem da lista. No update, se "etapas" for enviado,
    elas são substituídas por completo.
    """
    etapas = EtapaFluxoSerializer(many=True)
    criado_por = serializers.StringRelatedField(read_only=True)
    total_instancias = serializers.SerializerMethodField()

    class Meta:
        model = FluxoPadrao
        fields = ["id", "nome", "descricao", "etapas", "criado_por", "criado_em",
                  "atualizado_em", "total_instancias"]
        read_only_fields = ["id", "criado_por", "criado_em", "atualizado_em"]

    def get_total_instancias(self, obj) -> int:
        return obj.instancias.count()

    def validate_etapas(self, etapas):
        if not etapas:
            raise serializers.ValidationError("O modelo precisa de pelo menos uma etapa.")
        empresa = empresa_do_request(self)
        for e in etapas:
            if e.get("setor") and e["setor"].empresa_id != empresa.id:
                raise serializers.ValidationError("Setor de etapa não pertence à sua empresa.")
        return etapas

    def _salvar_etapas(self, fluxo, etapas):
        fluxo.etapas.all().delete()
        for i, e in enumerate(etapas, start=1):
            EtapaFluxo.objects.create(fluxo=fluxo, ordem_etapa=i, **e)

    @transaction.atomic
    def create(self, validated_data):
        etapas = validated_data.pop("etapas")
        request = self.context["request"]
        fluxo = FluxoPadrao.objects.create(
            empresa=request.user.empresa, criado_por=request.user, **validated_data
        )
        self._salvar_etapas(fluxo, etapas)
        return fluxo

    @transaction.atomic
    def update(self, instance, validated_data):
        etapas = validated_data.pop("etapas", None)
        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.atualizado_em = timezone.now()
        instance.save()
        if etapas is not None:
            self._salvar_etapas(instance, etapas)
        return instance


# ==========================================================
# Instâncias (fluxos em execução)
# ==========================================================
class UsuarioResumoSerializer(serializers.ModelSerializer):
    nome = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = ["id", "username", "nome"]

    def get_nome(self, obj) -> str:
        return obj.get_full_name() or obj.username


class EtapaInstanciaSerializer(serializers.ModelSerializer):
    setor_detalhe = SetorResumoSerializer(source="setor", read_only=True)
    status = serializers.SerializerMethodField()

    class Meta:
        model = EtapaInstancia
        fields = ["id", "ordem_etapa", "nome", "setor_detalhe", "perfil_aprovador", "concluida", "status"]

    def get_status(self, obj) -> str:
        """concluida | atual | pendente"""
        if obj.concluida:
            return "concluida"
        atual_id = self.context.get("etapa_atual_id")
        return "atual" if obj.id == atual_id else "pendente"


class MovimentacaoSerializer(serializers.ModelSerializer):
    acao = serializers.CharField(source="acao.nome", default=None)
    etapa = serializers.CharField(source="etapa.nome", default=None)
    etapa_id = serializers.IntegerField(source="etapa.id", default=None)
    usuario = UsuarioResumoSerializer(read_only=True)

    class Meta:
        model = MovimentacaoFluxo
        fields = ["id", "acao", "etapa", "etapa_id", "usuario", "comentario", "data_acao"]


class FluxoInstanciaListSerializer(serializers.ModelSerializer):
    modelo = serializers.CharField(source="modelo.nome", read_only=True)
    criado_por = UsuarioResumoSerializer(read_only=True)
    etapa_atual = serializers.SerializerMethodField()
    progresso = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = FluxoInstancia
        fields = ["id", "nome", "modelo", "status", "finalizado", "etapa_atual", "progresso",
                  "criado_por", "criado_em", "atualizado_em"]

    def _etapas(self, obj):
        return sorted(obj.etapas.all(), key=lambda e: e.ordem_etapa)

    def get_status(self, obj) -> str:
        return "finalizado" if obj.finalizado else "em_andamento"

    def get_etapa_atual(self, obj) -> dict | None:
        atual = next((e for e in self._etapas(obj) if not e.concluida), None)
        if not atual:
            return None
        return {"id": atual.id, "nome": atual.nome, "ordem_etapa": atual.ordem_etapa,
                "setor": atual.setor.nome if atual.setor else None}

    def get_progresso(self, obj) -> dict:
        etapas = self._etapas(obj)
        return {"concluidas": sum(1 for e in etapas if e.concluida), "total": len(etapas)}


class FluxoInstanciaDetailSerializer(FluxoInstanciaListSerializer):
    etapas = serializers.SerializerMethodField()
    movimentacoes = serializers.SerializerMethodField()
    pode_aprovar = serializers.SerializerMethodField()
    pode_retornar = serializers.SerializerMethodField()

    class Meta(FluxoInstanciaListSerializer.Meta):
        fields = FluxoInstanciaListSerializer.Meta.fields + [
            "etapas", "movimentacoes", "pode_aprovar", "pode_retornar"]

    def _atual(self, obj):
        if not hasattr(obj, "_atual_cache"):
            obj._atual_cache = next((e for e in self._etapas(obj) if not e.concluida), None)
        return obj._atual_cache

    def get_etapas(self, obj) -> list:
        atual = self._atual(obj)
        ctx = {**self.context, "etapa_atual_id": atual.id if atual else None}
        return EtapaInstanciaSerializer(self._etapas(obj), many=True, context=ctx).data

    def get_movimentacoes(self, obj) -> list:
        qs = obj.movimentacoes.select_related("acao", "etapa", "usuario").order_by("-data_acao")
        return MovimentacaoSerializer(qs, many=True).data

    def get_pode_aprovar(self, obj) -> bool:
        return services.pode_aprovar(self.context["request"].user, self._atual(obj))

    def get_pode_retornar(self, obj) -> bool:
        atual = self._atual(obj)
        return bool(atual and atual.ordem_etapa > 1 and self.get_pode_aprovar(obj))


class FluxoInstanciaCreateSerializer(serializers.Serializer):
    modelo = serializers.PrimaryKeyRelatedField(queryset=FluxoPadrao.objects.all())
    nome = serializers.CharField(max_length=200)
    comentario = serializers.CharField(required=False, allow_blank=True)

    def validate_modelo(self, modelo):
        if modelo.empresa_id != empresa_do_request(self).id:
            raise serializers.ValidationError("Modelo não encontrado.")
        return modelo


class MovimentarSerializer(serializers.Serializer):
    comentario = serializers.CharField(required=False, allow_blank=True)
    etapa_id = serializers.IntegerField(
        required=False,
        help_text="Opcional: id da etapa que o app está exibindo. Evita aprovar uma etapa "
                  "que já mudou enquanto o usuário estava com a tela aberta.",
    )


# ==========================================================
# Notificações / Push
# ==========================================================
class NotificacaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notificacao
        fields = ["id", "tipo", "titulo", "mensagem", "fluxo_instancia", "lida", "criado_em"]
        read_only_fields = fields


class DispositivoPushSerializer(serializers.ModelSerializer):
    class Meta:
        model = DispositivoPush
        fields = ["id", "token", "plataforma", "ativo", "criado_em"]
        read_only_fields = ["id", "ativo", "criado_em"]
        extra_kwargs = {"token": {"validators": []}}
