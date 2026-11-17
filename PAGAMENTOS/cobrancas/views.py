import json

from django.conf import settings
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import mixins, permissions, serializers, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import PLANOS, Cobranca


# ==========================================================
# Permissões a partir das claims do JWT da API principal
# ==========================================================
class TemEmpresa(permissions.BasePermission):
    message = "Token sem empresa."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.auth.get("empresa_id"))


class AdminEmpresaParaEscrever(permissions.BasePermission):
    message = "Apenas administradores da empresa podem contratar planos."

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.auth.get("perfil") == "administrador"


# ==========================================================
# Serializers
# ==========================================================
class HistoricoSerializer(serializers.Serializer):
    status = serializers.CharField()
    origem = serializers.CharField()
    criado_em = serializers.DateTimeField()


class CobrancaSerializer(serializers.ModelSerializer):
    valor_formatado = serializers.CharField(read_only=True)
    historico = HistoricoSerializer(many=True, read_only=True)

    class Meta:
        model = Cobranca
        fields = ["id", "plano", "valor", "valor_formatado", "status", "gateway", "checkout_url",
                  "email", "criado_em", "atualizado_em", "historico"]


class CriarCobrancaSerializer(serializers.Serializer):
    plano = serializers.ChoiceField(choices=list(PLANOS))
    return_url = serializers.URLField(required=False)
    cnpj = serializers.CharField(required=False, allow_blank=True)
    telefone = serializers.CharField(required=False, allow_blank=True)


# ==========================================================
# API
# ==========================================================
@extend_schema(tags=["Planos"])
class PlanosView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    @extend_schema(responses=inline_serializer("Plano", {
        "plano": serializers.CharField(), "nome": serializers.CharField(), "valor": serializers.IntegerField()}, many=True))
    def get(self, request):
        """Planos pagos disponíveis (preço em centavos)."""
        return Response([{"plano": k, "nome": n, "valor": v} for k, (n, v) in PLANOS.items()])


@extend_schema(tags=["Cobranças"])
class CobrancaViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                      viewsets.GenericViewSet):
    """
    Cobranças da empresa do usuário logado (token da API principal).
    Criar = gerar o link de pagamento PIX. Cada mudança de status vira um
    evento no RabbitMQ (e um e-mail para o cliente).
    """
    serializer_class = CobrancaSerializer
    permission_classes = [permissions.IsAuthenticated, TemEmpresa, AdminEmpresaParaEscrever]
    queryset = Cobranca.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Cobranca.objects.none()
        return Cobranca.objects.filter(empresa_id=self.request.auth["empresa_id"]).prefetch_related("historico")

    @extend_schema(request=CriarCobrancaSerializer, responses={201: CobrancaSerializer})
    def create(self, request, *args, **kwargs):
        ser = CriarCobrancaSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            c = services.criar_cobranca(request.auth, **ser.validated_data)
        except services.CobrancaError as e:
            raise ValidationError({"detail": str(e)})
        return Response(CobrancaSerializer(c).data, status=status.HTTP_201_CREATED)


@csrf_exempt
@require_POST
def webhook_abacatepay(request):
    secret = request.GET.get("secret") or request.GET.get("webhookSecret")
    if not settings.WEBHOOK_SECRET or secret != settings.WEBHOOK_SECRET:
        return JsonResponse({"error": "invalid secret"}, status=401)
    try:
        payload = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "invalid json"}, status=400)
    return JsonResponse(services.processar_webhook_abacatepay(payload))


# ==========================================================
# Simulador (substitui o AbacatePay em desenvolvimento / apresentação)
# ==========================================================
ACOES_SIMULADOR = {"pagar": Cobranca.PAGO, "cancelar": Cobranca.CANCELADO,
                   "expirar": Cobranca.EXPIRADO, "reembolsar": Cobranca.REEMBOLSADO}


@csrf_exempt
def simulador(request, pk):
    if not settings.SIMULADOR_ATIVO:
        raise Http404
    c = get_object_or_404(Cobranca, pk=pk)
    erro = None
    if request.method == "POST":
        novo = ACOES_SIMULADOR.get(request.POST.get("acao"))
        try:
            if novo:
                services.mudar_status(c, novo, "simulador")
            return redirect(request.path)
        except services.CobrancaError as e:
            erro = str(e)
    c.refresh_from_db()
    acoes = [a for a, st in ACOES_SIMULADOR.items() if st in Cobranca.TRANSICOES[c.status]]
    return render(request, "cobrancas/simulador.html", {"c": c, "acoes": acoes, "erro": erro})
