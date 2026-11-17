from rest_framework.permissions import SAFE_METHODS, BasePermission


class TemEmpresa(BasePermission):
    """Usuário precisa estar vinculado a uma empresa ativa."""
    message = "Usuário sem empresa vinculada."

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.empresa_id and u.empresa.ativo)


class EhAdminEmpresa(BasePermission):
    message = "Apenas administradores da empresa podem fazer isso."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_admin_empresa)


class AdminOuSomenteLeitura(BasePermission):
    """Todos da empresa leem; só administradores escrevem."""
    message = "Apenas administradores da empresa podem alterar estes dados."

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_admin_empresa)
