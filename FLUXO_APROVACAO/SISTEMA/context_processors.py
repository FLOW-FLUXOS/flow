def notificacoes(request):
    """Disponibiliza o número de notificações não lidas em todas as telas (sininho da sidebar)."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    return {"notificacoes_nao_lidas": user.notificacoes.filter(lida=False).count()}
