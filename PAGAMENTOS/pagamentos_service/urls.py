"""
Todas as rotas ficam sob /api/pagamentos/ — assim o gateway (nginx) só repassa o caminho.
"""
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from cobrancas import views

router = DefaultRouter()
router.register("cobrancas", views.CobrancaViewSet, basename="cobranca")

urlpatterns = [
    path("api/pagamentos/admin/", admin.site.urls),
    path("api/pagamentos/planos/", views.PlanosView.as_view(), name="planos"),
    path("api/pagamentos/webhook/abacatepay/", views.webhook_abacatepay, name="webhook-abacatepay"),
    path("api/pagamentos/simulador/<uuid:pk>/", views.simulador, name="simulador"),
    path("api/pagamentos/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/pagamentos/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    path("api/pagamentos/", include(router.urls)),
]
