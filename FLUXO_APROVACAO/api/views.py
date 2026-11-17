from django.db.models import Prefetch
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import generics, mixins, permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from SISTEMA import services
from SISTEMA.models import (
    DispositivoPush,
    EtapaInstancia,
    FluxoInstancia,
    FluxoPadrao,
    Notificacao,
    Setor,
    Usuario,
)

from . import serializers as s
from .permissions import AdminOuSomenteLeitura, EhAdminEmpresa, TemEmpresa


def converter_erro(exc):
    """Traduz erros da camada de serviço para respostas HTTP."""
    if isinstance(exc, services.PermissaoNegadaError):
        return PermissionDenied(str(exc))
    return ValidationError({"detail": str(exc)})


class EmpresaQuerysetMixin:
    """Garante que cada empresa só enxerga os próprios dados (multi-tenant)."""
    permission_classes = [permissions.IsAuthenticated, TemEmpresa]

    def get_queryset(self):
        return super().get_queryset().filter(empresa_id=self.request.user.empresa_id)


# ==========================================================
# Autenticação
# ==========================================================
@extend_schema(tags=["Auth"])
class LoginView(TokenObtainPairView):
    """Login com usuário e senha. Retorna `access`, `refresh` e os dados do usuário."""
    serializer_class = s.LoginSerializer


@extend_schema(tags=["Auth"], responses={201: s.MeSerializer})
class RegistroView(generics.GenericAPIView):
    """Cria uma nova empresa e o seu primeiro administrador (plano Freemium)."""
    serializer_class = s.RegistroSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = ser.save()
        return Response(s.MeSerializer(user).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Auth"])
class MeView(generics.RetrieveUpdateAPIView):
    """Dados do usuário logado (GET) e edição do próprio perfil (PATCH)."""
    serializer_class = s.MeSerializer
    http_method_names = ["get", "patch"]

    def get_object(self):
        return self.request.user


@extend_schema(tags=["Auth"], responses={204: None})
class TrocarSenhaView(generics.GenericAPIView):
    serializer_class = s.TrocarSenhaSerializer

    def post(self, request):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        request.user.set_password(ser.validated_data["nova_senha"])
        request.user.save(update_fields=["password"])
        return Response(status=status.HTTP_204_NO_CONTENT)


# ==========================================================
# Empresa / Assinatura
# ==========================================================
@extend_schema(tags=["Empresa"])
class EmpresaView(generics.RetrieveUpdateAPIView):
    """Empresa do usuário logado. Só administradores podem alterar."""
    serializer_class = s.EmpresaSerializer
    permission_classes = [permissions.IsAuthenticated, TemEmpresa, AdminOuSomenteLeitura]
    http_method_names = ["get", "patch"]

    def get_object(self):
        return self.request.user.empresa


@extend_schema(tags=["Assinatura"])
class AssinaturaView(APIView):
    """Plano atual da empresa. Para contratar um plano use o microserviço: POST /api/pagamentos/cobrancas/"""
    permission_classes = [permissions.IsAuthenticated, TemEmpresa]

    @extend_schema(responses=inline_serializer("AssinaturaAtual", {
        "plano_atual": serializers.CharField(),
        "limite_usuarios": serializers.IntegerField(allow_null=True),
        "total_usuarios": serializers.IntegerField(),
        "assinatura": s.AssinaturaSerializer(allow_null=True),
    }))
    def get(self, request):
        empresa = request.user.empresa
        assinatura = empresa.assinatura_atual()
        return Response({
            "plano_atual": empresa.plano_atual,
            "limite_usuarios": empresa.limite_usuarios,
            "total_usuarios": empresa.total_usuarios,
            "assinatura": s.AssinaturaSerializer(assinatura).data if assinatura else None,
        })


# ==========================================================
# Cadastros
# ==========================================================
@extend_schema(tags=["Setores"])
class SetorViewSet(EmpresaQuerysetMixin, viewsets.ModelViewSet):
    queryset = Setor.objects.all().order_by("nome")
    serializer_class = s.SetorSerializer
    permission_classes = EmpresaQuerysetMixin.permission_classes + [AdminOuSomenteLeitura]
    search_fields = ["nome"]

    def perform_create(self, serializer):
        serializer.save(empresa=self.request.user.empresa)


@extend_schema(tags=["Usuários"])
class UsuarioViewSet(EmpresaQuerysetMixin, viewsets.ModelViewSet):
    """Usuários da empresa. Listar: todos. Criar/editar/excluir: administradores."""
    queryset = Usuario.objects.select_related("setor").order_by("username")
    serializer_class = s.UsuarioSerializer
    permission_classes = EmpresaQuerysetMixin.permission_classes + [AdminOuSomenteLeitura]
    search_fields = ["username", "first_name", "last_name", "email"]
    filterset_fields = ["setor", "perfil", "is_active"]

    def perform_destroy(self, instance):
        if instance.pk == self.request.user.pk:
            raise ValidationError({"detail": "Você não pode excluir o próprio usuário."})
        instance.delete()


@extend_schema(tags=["Modelos de fluxo"])
class FluxoPadraoViewSet(EmpresaQuerysetMixin, viewsets.ModelViewSet):
    queryset = FluxoPadrao.objects.select_related("criado_por").prefetch_related(
        "etapas__setor").order_by("-criado_em")
    serializer_class = s.FluxoPadraoSerializer
    permission_classes = EmpresaQuerysetMixin.permission_classes + [AdminOuSomenteLeitura]
    search_fields = ["nome", "descricao"]


# ==========================================================
# Fluxos em execução
# ==========================================================
@extend_schema(tags=["Fluxos"])
class FluxoInstanciaViewSet(EmpresaQuerysetMixin,
                            mixins.ListModelMixin,
                            mixins.RetrieveModelMixin,
                            mixins.CreateModelMixin,
                            mixins.DestroyModelMixin,
                            viewsets.GenericViewSet):
    """
    Fluxos em execução. Qualquer usuário cria e acompanha; quem é aprovador
    da etapa atual pode avançar/retornar; só administradores excluem.
    """
    queryset = FluxoInstancia.objects.select_related("modelo", "criado_por").prefetch_related(
        Prefetch("etapas", queryset=EtapaInstancia.objects.select_related("setor"))
    )
    search_fields = ["nome", "modelo__nome"]
    ordering_fields = ["criado_em", "atualizado_em", "nome"]
    ordering = ["-criado_em"]

    def get_serializer_class(self):
        if self.action == "create":
            return s.FluxoInstanciaCreateSerializer
        if self.action in ("retrieve", "avancar", "retornar"):
            return s.FluxoInstanciaDetailSerializer
        return s.FluxoInstanciaListSerializer

    def get_permissions(self):
        perms = super().get_permissions()
        if self.action == "destroy":
            perms.append(EhAdminEmpresa())
        return perms

    @extend_schema(parameters=[
        OpenApiParameter("status", str, enum=["em_andamento", "finalizado"]),
        OpenApiParameter("minhas", bool, description="Só os fluxos que eu criei"),
        OpenApiParameter("modelo", int),
    ])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action != "list":
            return qs
        p = self.request.query_params
        if p.get("status") == "em_andamento":
            qs = qs.filter(finalizado=False)
        elif p.get("status") == "finalizado":
            qs = qs.filter(finalizado=True)
        if p.get("minhas") in ("1", "true", "True"):
            qs = qs.filter(criado_por=self.request.user)
        if p.get("modelo"):
            qs = qs.filter(modelo_id=p["modelo"])
        return qs

    @extend_schema(request=s.FluxoInstanciaCreateSerializer, responses={201: s.FluxoInstanciaDetailSerializer})
    def create(self, request, *args, **kwargs):
        ser = s.FluxoInstanciaCreateSerializer(data=request.data, context=self.get_serializer_context())
        ser.is_valid(raise_exception=True)
        try:
            instancia = services.criar_instancia(
                request.user, ser.validated_data["modelo"], ser.validated_data["nome"],
                ser.validated_data.get("comentario", ""),
            )
        except services.RegraNegocioError as e:
            raise converter_erro(e)
        instancia = self.get_queryset().get(pk=instancia.pk)
        data = s.FluxoInstanciaDetailSerializer(instancia, context=self.get_serializer_context()).data
        return Response(data, status=status.HTTP_201_CREATED)

    @extend_schema(responses=s.FluxoInstanciaListSerializer(many=True))
    @action(detail=False, methods=["get"])
    def pendentes(self, request):
        """Fluxos que estão esperando a MINHA aprovação (tela principal do app)."""
        qs = services.instancias_pendentes_para(request.user).select_related(
            "modelo", "criado_por").prefetch_related("etapas__setor").order_by("-atualizado_em")
        page = self.paginate_queryset(qs)
        ser = s.FluxoInstanciaListSerializer(page, many=True, context=self.get_serializer_context())
        return self.get_paginated_response(ser.data)

    def _movimentar(self, request, funcao):
        instancia = self.get_object()
        ser = s.MovimentarSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            funcao(request.user, instancia, ser.validated_data.get("comentario", ""),
                   etapa_id=ser.validated_data.get("etapa_id"))
        except services.RegraNegocioError as e:
            raise converter_erro(e)
        instancia = self.get_queryset().get(pk=instancia.pk)
        return Response(s.FluxoInstanciaDetailSerializer(instancia, context=self.get_serializer_context()).data)

    @extend_schema(request=s.MovimentarSerializer, responses=s.FluxoInstanciaDetailSerializer)
    @action(detail=True, methods=["post"])
    def avancar(self, request, pk=None):
        """Aprova a etapa atual e avança o fluxo (finaliza se for a última)."""
        return self._movimentar(request, services.avancar)

    @extend_schema(request=s.MovimentarSerializer, responses=s.FluxoInstanciaDetailSerializer)
    @action(detail=True, methods=["post"])
    def retornar(self, request, pk=None):
        """Devolve o fluxo para a etapa anterior."""
        return self._movimentar(request, services.retornar)


# ==========================================================
# Notificações (geradas pelo worker a partir do RabbitMQ)
# ==========================================================
@extend_schema(tags=["Notificações"])
class NotificacaoViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Notificacao.objects.none()
    serializer_class = s.NotificacaoSerializer
    permission_classes = [permissions.IsAuthenticated, TemEmpresa]
    filterset_fields = ["lida", "tipo"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Notificacao.objects.none()
        return Notificacao.objects.filter(usuario=self.request.user).order_by("-criado_em")

    @extend_schema(responses=inline_serializer("ContagemNaoLidas", {"nao_lidas": serializers.IntegerField()}))
    @action(detail=False, methods=["get"], url_path="nao-lidas")
    def nao_lidas(self, request):
        """Contador para o badge do sininho."""
        return Response({"nao_lidas": self.get_queryset().filter(lida=False).count()})

    @extend_schema(request=None, responses=s.NotificacaoSerializer)
    @action(detail=True, methods=["post"])
    def ler(self, request, pk=None):
        n = generics.get_object_or_404(self.get_queryset(), pk=pk)
        n.lida = True
        n.save(update_fields=["lida"])
        return Response(s.NotificacaoSerializer(n).data)

    @extend_schema(request=None, responses=inline_serializer("LerTodas", {"atualizadas": serializers.IntegerField()}))
    @action(detail=False, methods=["post"], url_path="ler-todas")
    def ler_todas(self, request):
        total = self.get_queryset().filter(lida=False).update(lida=True)
        return Response({"atualizadas": total})


@extend_schema(tags=["Notificações"])
class DispositivoPushViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                             mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """O app registra aqui o token do Firebase Cloud Messaging após o login."""
    queryset = DispositivoPush.objects.none()
    serializer_class = s.DispositivoPushSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return DispositivoPush.objects.none()
        return DispositivoPush.objects.filter(usuario=self.request.user)

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        disp, _ = DispositivoPush.objects.update_or_create(
            token=ser.validated_data["token"],
            defaults={"usuario": request.user, "plataforma": ser.validated_data.get("plataforma", "android"),
                      "ativo": True},
        )
        return Response(self.get_serializer(disp).data, status=status.HTTP_201_CREATED)
