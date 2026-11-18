"""
Rotas das telas. Cada rota só devolve o template; nenhuma view consulta dados.
Quem é admin ou não é decidido pela API (o front só esconde o que não faz sentido mostrar).
"""
from django.templatetags.static import static
from django.urls import path
from django.views.generic import RedirectView, TemplateView


def tela(template):
    return TemplateView.as_view(template_name=template)


urlpatterns = [
    path("favicon.ico", RedirectView.as_view(url=static("img/FLOW - ICONE.png").replace("%", "%%"))),
    # acesso
    path("login/", tela("login.html"), name="login"),
    path("registro/", tela("registro.html"), name="registro"),
    # colaborador
    path("", tela("home.html"), name="home"),
    path("fluxos/instancias/", tela("fluxos_lista.html"), name="fluxos"),
    path("fluxos/instancias/novo/", tela("fluxo_novo.html"), name="fluxo_novo"),
    path("fluxos/instancias/<int:id>/", tela("fluxo_detalhe.html"), name="fluxo_detalhe"),
    path("notificacoes/", tela("notificacoes.html"), name="notificacoes"),
    path("perfil/", tela("perfil.html"), name="perfil"),
    # backoffice (admin)
    path("setores/", tela("setores.html"), name="setores"),
    path("usuarios/", tela("usuarios.html"), name="usuarios"),
    path("usuarios/novo/", tela("usuario_form.html"), name="usuario_novo"),
    path("usuarios/<int:id>/editar/", tela("usuario_form.html"), name="usuario_editar"),
    path("fluxos/modelos/", tela("modelos.html"), name="modelos"),
    path("fluxos/modelos/novo/", tela("modelo_form.html"), name="modelo_novo"),
    path("fluxos/modelos/<int:id>/editar/", tela("modelo_form.html"), name="modelo_editar"),
    path("assinatura/", tela("planos.html"), name="planos"),
]
