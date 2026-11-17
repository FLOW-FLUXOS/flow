"""
Claims extras do JWT. O microserviço de pagamentos não tem tabela de usuários:
ele confia nessas informações, que vêm assinadas com a chave compartilhada.
"""
from rest_framework_simplejwt.tokens import RefreshToken


def adicionar_claims(token, user):
    token["empresa_id"] = user.empresa_id
    token["empresa_nome"] = user.empresa.nome if user.empresa_id else ""
    token["perfil"] = "administrador" if user.is_admin_empresa else "padrao"
    token["email"] = user.email or ""
    token["nome"] = user.get_full_name() or user.username
    return token


def access_token_para(user) -> str:
    """Token de acesso usado pelo web (servidor) ao chamar outros serviços em nome do usuário."""
    refresh = adicionar_claims(RefreshToken.for_user(user), user)
    return str(refresh.access_token)
