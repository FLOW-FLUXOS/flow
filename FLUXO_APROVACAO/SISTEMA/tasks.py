"""
Consumidores das filas do RabbitMQ (executados pelo worker Celery).
"""
import logging

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def processar_evento_fluxo(self, tipo, instancia_id, usuario_id=None, etapa_id=None):
    """Fila fluxo.eventos — decide quem precisa ser notificado e cria as notificações."""
    from .models import EtapaInstancia, FluxoInstancia, Notificacao, Usuario
    from .services import aprovadores_da_etapa, etapa_atual

    try:
        instancia = FluxoInstancia.objects.select_related("criado_por").get(pk=instancia_id)
    except FluxoInstancia.DoesNotExist:
        logger.warning("Evento %s ignorado: fluxo %s não existe mais", tipo, instancia_id)
        return 0

    autor = Usuario.objects.filter(pk=usuario_id).first() if usuario_id else None
    nome_autor = (autor.get_full_name() or autor.username) if autor else "Sistema"
    destinos = {}  # usuario_id -> (tipo, titulo, mensagem)

    def avisar(usuarios, tipo_notif, titulo, mensagem):
        for u in usuarios:
            if autor and u.pk == autor.pk:
                continue  # não notifica quem fez a ação
            destinos.setdefault(u.pk, (tipo_notif, titulo, mensagem))

    # Etapa do momento do evento (a fila pode atrasar e o fluxo já ter andado)
    atual = EtapaInstancia.objects.filter(pk=etapa_id, fluxo_instancia=instancia).first() if etapa_id else None
    agora = etapa_atual(instancia)
    ainda_pendente = bool(atual and agora and agora.pk == atual.pk)

    if tipo in ("criado", "avancado", "retornado") and ainda_pendente:
        verbo = "retornou para" if tipo == "retornado" else "aguarda sua aprovação em"
        avisar(
            aprovadores_da_etapa(atual),
            "etapa_pendente",
            f"Aprovação pendente: {instancia.nome}",
            f"O fluxo \"{instancia.nome}\" {verbo} \"{atual.nome}\".",
        )

    if instancia.criado_por:
        if tipo == "avancado" and atual:
            avisar([instancia.criado_por], "fluxo_avancado", f"Fluxo avançou: {instancia.nome}",
                   f"{nome_autor} aprovou e o fluxo seguiu para \"{atual.nome}\".")
        elif tipo == "retornado" and atual:
            avisar([instancia.criado_por], "fluxo_retornado", f"Fluxo retornado: {instancia.nome}",
                   f"{nome_autor} devolveu o fluxo para \"{atual.nome}\".")
        elif tipo == "finalizado":
            avisar([instancia.criado_por], "fluxo_finalizado", f"Fluxo finalizado: {instancia.nome}",
                   f"Todas as etapas foram aprovadas. Última aprovação por {nome_autor}.")

    criadas = [
        Notificacao(
            empresa_id=instancia.empresa_id, usuario_id=uid, tipo=t, titulo=titulo,
            mensagem=msg, fluxo_instancia=instancia,
        )
        for uid, (t, titulo, msg) in destinos.items()
    ]
    criadas = Notificacao.objects.bulk_create(criadas)

    if settings.FIREBASE_CREDENTIALS:
        for n in criadas:
            if n.pk:
                enviar_push.delay(n.pk)

    logger.info("Evento %s do fluxo %s -> %d notificação(ões)", tipo, instancia_id, len(criadas))
    return len(criadas)


_firebase_app = None


def _firebase():
    global _firebase_app
    if _firebase_app is None:
        import firebase_admin
        from firebase_admin import credentials

        _firebase_app = firebase_admin.initialize_app(credentials.Certificate(settings.FIREBASE_CREDENTIALS))
    return _firebase_app


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def enviar_push(self, notificacao_id):
    """Fila notificacoes.push — envia a notificação para os celulares do usuário (FCM)."""
    from .models import DispositivoPush, Notificacao

    if not settings.FIREBASE_CREDENTIALS:
        return 0
    try:
        from firebase_admin import messaging
    except ImportError:
        logger.warning("firebase-admin não instalado; push ignorado")
        return 0

    n = Notificacao.objects.filter(pk=notificacao_id).first()
    if not n:
        return 0
    enviados = 0
    for disp in DispositivoPush.objects.filter(usuario_id=n.usuario_id, ativo=True):
        msg = messaging.Message(
            token=disp.token,
            notification=messaging.Notification(title=n.titulo, body=n.mensagem),
            data={"notificacao_id": str(n.pk), "tipo": n.tipo,
                  "fluxo_instancia_id": str(n.fluxo_instancia_id or "")},
        )
        try:
            messaging.send(msg, app=_firebase())
            enviados += 1
        except messaging.UnregisteredError:
            disp.ativo = False
            disp.save(update_fields=["ativo"])
        except Exception as exc:
            raise self.retry(exc=exc)
    return enviados
