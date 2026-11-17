"""
Rotas do FLOW.

  /api/v1/   -> API REST (app Flutter / qualquer front)   docs: /api/v1/docs/
  /admin/    -> Django Admin (dono da plataforma / superusuário)
  /          -> Backoffice web (administradores das empresas)
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('api.urls')),
    path('', include('SISTEMA.urls')),
]
