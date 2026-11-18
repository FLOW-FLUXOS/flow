from django.conf import settings


def config(request):
    """Endereços das APIs, entregues ao JavaScript da página."""
    return {"FLOW_API_URL": settings.FLOW_API_URL, "FLOW_PAGAMENTOS_URL": settings.FLOW_PAGAMENTOS_URL}
