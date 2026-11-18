"""
Rotas da API principal do FLOW.

  /api/v1/   -> API REST (consumida pelo web, pelo app Flutter e pelo Swagger)
  /admin/    -> Django Admin (dono da plataforma / superusuário)

As telas do sistema ficam no projeto WEB, que só conversa com esta API.
"""
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('api.urls')),
    path('', RedirectView.as_view(url='/api/v1/docs/', permanent=False)),
]
