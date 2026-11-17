# SISTEMA/views.py — Sistema web
#   Todos os usuários: fluxos (criar, acompanhar, aprovar), notificações
#   Somente administradores: usuários, setores, modelos de fluxo, planos
from functools import wraps

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import pagamentos_client, services
from .forms import (
    FluxoPadraoForm,
    InstanciaFluxoForm,
    LoginForm,
    SetorForm,
    UsuarioCreateForm,
    UsuarioEditForm,
)
from .models import EtapaFluxo, FluxoInstancia, FluxoPadrao, Notificacao, Setor, Usuario


def empresa_required(view):
    """Qualquer usuário logado e vinculado a uma empresa ativa."""
    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.empresa_id or not user.empresa.ativo:
            logout(request)
            messages.error(request, "Usuário sem empresa ativa vinculada.")
            return redirect("login")
        return view(request, *args, **kwargs)
    return wrapper


def admin_required(view):
    """Área de gestão: além de ter empresa, precisa ser administrador."""
    @empresa_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_admin_empresa:
            messages.error(request, "Apenas administradores podem acessar essa área.")
            return redirect("home")
        return view(request, *args, **kwargs)
    return wrapper


## Login
def login_view(request):
    form = LoginForm(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            user = authenticate(request, username=form.cleaned_data['username'],
                                password=form.cleaned_data['password'])
            if user is None:
                messages.error(request, "Usuário ou senha incorretos.")
            elif not user.empresa_id:
                messages.error(request, "Usuário sem empresa vinculada.")
            else:
                login(request, user)
                return redirect("home")

    return render(request, "login.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("login")


@empresa_required
def home_view(request):
    pendentes = services.instancias_pendentes_para(request.user).count()
    return render(request, "home.html", {"pendentes": pendentes})


## CRUD do Usuário
@admin_required
def criar_usuario(request):
    empresa = request.user.empresa
    form = UsuarioCreateForm(request.POST or None, empresa=empresa)
    if request.method == 'POST':
        if not empresa.pode_adicionar_usuario():
            messages.error(request, f'Seu plano ({empresa.plano_atual.title()}) permite até '
                                    f'{empresa.limite_usuarios} usuário(s). Faça upgrade em Planos.')
        elif form.is_valid():
            form.save()
            messages.success(request, 'Usuário criado com sucesso!')
            return redirect('listar_usuarios')
        else:
            messages.error(request, 'Erro ao criar usuário. Verifique os campos.')
    return render(request, 'usuario_criar.html', {'form': form})


@admin_required
def listar_usuarios(request):
    usuarios = Usuario.objects.filter(empresa=request.user.empresa).order_by('username')
    return render(request, 'usuario_listar.html', {'usuarios': usuarios})


@admin_required
def editar_usuario(request, id):
    usuario = get_object_or_404(Usuario, id=id, empresa=request.user.empresa)
    form = UsuarioEditForm(request.POST or None, instance=usuario, empresa=request.user.empresa)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('listar_usuarios')
    return render(request, 'usuario_editar.html', {'form': form, 'usuario': usuario})


@admin_required
def deletar_usuario(request, id):
    usuario = get_object_or_404(Usuario, id=id, empresa=request.user.empresa)
    if request.method == 'POST':
        if usuario.pk == request.user.pk:
            messages.error(request, 'Você não pode excluir o próprio usuário.')
        else:
            usuario.delete()
        return redirect('listar_usuarios')
    return render(request, 'usuario_excluir.html', {'usuario': usuario})


## CRUD do Setor
@admin_required
def listar_setores(request):
    setores = Setor.objects.filter(empresa=request.user.empresa).order_by('nome')
    return render(request, 'setor_listar.html', {'setores': setores})


@admin_required
def criar_setor(request):
    form = SetorForm(request.POST or None, empresa=request.user.empresa)
    if request.method == 'POST' and form.is_valid():
        setor = form.save(commit=False)
        setor.empresa = request.user.empresa
        setor.save()
        return redirect('listar_setores')
    return render(request, 'setor_criar.html', {'form': form, 'titulo': 'Criar Setor'})


@admin_required
def editar_setor(request, id):
    setor = get_object_or_404(Setor, id=id, empresa=request.user.empresa)
    form = SetorForm(request.POST or None, instance=setor, empresa=request.user.empresa)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('listar_setores')
    return render(request, 'setor_criar.html', {'form': form, 'titulo': 'Editar Setor'})


@admin_required
def deletar_setor(request, id):
    setor = get_object_or_404(Setor, id=id, empresa=request.user.empresa)
    if request.method == 'POST':
        setor.delete()
        return redirect('listar_setores')
    return render(request, 'setor_excluir.html', {'setor': setor})


## Modelos de fluxo
@admin_required
def listar_modelos_fluxo(request):
    fluxos = FluxoPadrao.objects.filter(empresa=request.user.empresa).order_by('-criado_em')
    return render(request, 'modelos_fluxo_listar.html', {'fluxos': fluxos})


@admin_required
def criar_modelos_fluxo(request):
    empresa = request.user.empresa
    setores = Setor.objects.filter(empresa=empresa).order_by('nome')
    form = FluxoPadraoForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        etapas_total = int(request.POST.get('num_etapas', 0) or 0)
        etapas = []
        for i in range(1, etapas_total + 1):
            nome = (request.POST.get(f'etapa_nome_{i}') or '').strip()
            setor_id = request.POST.get(f'etapa_setor_{i}') or None
            perfil = request.POST.get(f'etapa_perfil_{i}') or 'padrao'
            if setor_id and not setores.filter(id=setor_id).exists():
                setor_id = None
            if nome:
                etapas.append((nome, setor_id, perfil))
        if not etapas:
            messages.error(request, 'Informe pelo menos uma etapa.')
        else:
            fluxo = form.save(commit=False)
            fluxo.empresa = empresa
            fluxo.criado_por = request.user
            fluxo.save()
            for ordem, (nome, setor_id, perfil) in enumerate(etapas, start=1):
                EtapaFluxo.objects.create(fluxo=fluxo, ordem_etapa=ordem, nome=nome,
                                          setor_id=setor_id, perfil_aprovador=perfil,
                                          criado_em=timezone.now())
            messages.success(request, 'Fluxo modelo criado com sucesso!')
            return redirect('listar_modelos_fluxo')
    return render(request, 'modelos_fluxo_criar.html', {'form': form, 'setores': setores})


@admin_required
def excluir_modelos_fluxo(request, id):
    fluxo = get_object_or_404(FluxoPadrao, id=id, empresa=request.user.empresa)
    if request.method == 'POST':
        fluxo.delete()
        messages.success(request, 'Modelo de fluxo excluído com sucesso.')
        return redirect('listar_modelos_fluxo')
    return render(request, 'modelos_fluxo_excluir.html', {'fluxo': fluxo})


## Instâncias de fluxo (todos os usuários)
@empresa_required
def criar_instancia_fluxo(request):
    form = InstanciaFluxoForm(request.POST or None, empresa=request.user.empresa)
    if request.method == 'POST' and form.is_valid():
        try:
            instancia = services.criar_instancia(
                request.user, form.cleaned_data['fluxo_padrao'], form.cleaned_data['nome_instancia'])
            messages.success(request, f'Fluxo "{instancia.nome}" criado com sucesso!')
            return redirect('detalhar_instancia_fluxo', id=instancia.id)
        except services.RegraNegocioError as e:
            messages.error(request, str(e))
    return render(request, 'instancia_fluxo_criar.html', {'form': form})


@empresa_required
def listar_instancias_fluxo(request):
    """Fluxos da empresa: aguardando minha aprovação, em andamento e finalizados."""
    base = FluxoInstancia.objects.filter(empresa=request.user.empresa).select_related('modelo')
    return render(request, 'instancia_fluxo_listar.html', {
        'pendentes': services.instancias_pendentes_para(request.user).select_related('modelo').order_by('-atualizado_em'),
        'em_andamento': base.filter(finalizado=False).order_by('-criado_em'),
        'finalizados': base.filter(finalizado=True).order_by('-criado_em'),
        'aba': request.GET.get('aba', 'pendentes'),
    })


@admin_required
def excluir_instancias_fluxo(request, id):
    instancia = get_object_or_404(FluxoInstancia, id=id, empresa=request.user.empresa)
    if request.method == 'POST':
        nome = instancia.nome
        instancia.delete()
        messages.success(request, f'Fluxo "{nome}" excluído com sucesso!')
        return redirect('listar_instancias_fluxo')
    return render(request, 'instancia_fluxo_excluir.html', {'instancia': instancia})


@empresa_required
def detalhar_instancia_fluxo(request, id):
    """Detalhes de uma instância: timeline (etapas) e histórico."""
    instancia = get_object_or_404(FluxoInstancia, id=id, empresa=request.user.empresa)
    etapas = instancia.etapas.select_related('setor').order_by('ordem_etapa')
    etapa_atual = services.etapa_atual(instancia)
    movimentacoes = instancia.movimentacoes.select_related('acao', 'etapa', 'usuario').order_by('-data_acao')
    pode_aprovar = services.pode_aprovar(request.user, etapa_atual)
    return render(request, 'instancia_fluxo_detalhar.html', {
        'instancia': instancia,
        'etapas': etapas,
        'etapa_atual': etapa_atual,
        'movimentacoes': movimentacoes,
        'pode_aprovar': pode_aprovar,
        'pode_retornar': pode_aprovar and etapa_atual is not None and etapa_atual.ordem_etapa > 1,
    })


@empresa_required
@require_POST
def mover_etapa(request, instancia_id, etapa_id):
    """POST com acao in ('avancar','retornar') e comentario — usa a mesma regra da API."""
    instancia = get_object_or_404(FluxoInstancia, id=instancia_id, empresa=request.user.empresa)
    acao = request.POST.get('acao')
    comentario = request.POST.get('comentario', '')
    funcoes = {'avancar': services.avancar, 'retornar': services.retornar}
    if acao not in funcoes:
        messages.error(request, 'Ação inválida.')
        return redirect('detalhar_instancia_fluxo', id=instancia.id)
    try:
        instancia = funcoes[acao](request.user, instancia, comentario, etapa_id=etapa_id)
        if instancia.finalizado:
            messages.success(request, f'Instância "{instancia.nome}" finalizada.')
        else:
            atual = services.etapa_atual(instancia)
            messages.success(request, f'Instância agora na etapa "{atual.nome}".')
    except services.RegraNegocioError as e:
        messages.warning(request, str(e))
    return redirect('detalhar_instancia_fluxo', id=instancia.id)


## Notificações (todos os usuários)
@empresa_required
def notificacoes_view(request):
    notificacoes = Notificacao.objects.filter(usuario=request.user).select_related('fluxo_instancia')[:100]
    return render(request, 'notificacoes.html', {'notificacoes': notificacoes})


@empresa_required
def abrir_notificacao(request, id):
    n = get_object_or_404(Notificacao, id=id, usuario=request.user)
    if not n.lida:
        n.lida = True
        n.save(update_fields=['lida'])
    if n.fluxo_instancia_id:
        return redirect('detalhar_instancia_fluxo', id=n.fluxo_instancia_id)
    return redirect('notificacoes')


@empresa_required
@require_POST
def ler_todas_notificacoes(request):
    Notificacao.objects.filter(usuario=request.user, lida=False).update(lida=True)
    return redirect('notificacoes')


## Planos (admin) — os pagamentos ficam no microserviço de Pagamentos
@admin_required
def assinatura_view(request):
    empresa = request.user.empresa
    assinatura = empresa.assinatura_atual()
    try:
        cobrancas = pagamentos_client.listar_cobrancas(request.user)
        erro_pagamentos = None
    except pagamentos_client.PagamentosIndisponivel as e:
        cobrancas, erro_pagamentos = [], str(e)
    return render(request, 'assinaturas.html', {
        "empresa": empresa,
        "assinatura": assinatura,
        "dias_restantes": assinatura.dias_restantes if assinatura else None,
        "cobrancas": cobrancas,
        "erro_pagamentos": erro_pagamentos,
    })


def _checkout(request, plano):
    try:
        cobranca = pagamentos_client.criar_cobranca(
            request.user, plano, request.build_absolute_uri('/assinatura/'))
        return redirect(cobranca["checkout_url"])
    except pagamentos_client.PagamentosIndisponivel as e:
        messages.error(request, str(e))
        return redirect('assinatura_view')


@admin_required
@require_POST
def checkout_prata(request):
    return _checkout(request, "prata")


@admin_required
@require_POST
def checkout_ouro(request):
    return _checkout(request, "ouro")
