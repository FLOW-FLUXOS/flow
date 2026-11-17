from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenBlacklistView, TokenRefreshView

from . import views

router = DefaultRouter()
router.register("setores", views.SetorViewSet, basename="setor")
router.register("usuarios", views.UsuarioViewSet, basename="usuario")
router.register("modelos", views.FluxoPadraoViewSet, basename="modelo")
router.register("fluxos", views.FluxoInstanciaViewSet, basename="fluxo")
router.register("notificacoes", views.NotificacaoViewSet, basename="notificacao")
router.register("dispositivos", views.DispositivoPushViewSet, basename="dispositivo")

urlpatterns = [
    # Auth
    path("auth/login/", views.LoginView.as_view(), name="api-login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="api-refresh"),
    path("auth/logout/", TokenBlacklistView.as_view(), name="api-logout"),
    path("auth/registro/", views.RegistroView.as_view(), name="api-registro"),
    path("auth/me/", views.MeView.as_view(), name="api-me"),
    path("auth/trocar-senha/", views.TrocarSenhaView.as_view(), name="api-trocar-senha"),
    # Empresa / Assinatura
    path("empresa/", views.EmpresaView.as_view(), name="api-empresa"),
    path("assinatura/", views.AssinaturaView.as_view(), name="api-assinatura"),
    # Documentação
    path("schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="api-schema"), name="api-docs"),
    path("redoc/", SpectacularRedocView.as_view(url_name="api-schema"), name="api-redoc"),
    path("", include(router.urls)),
]
