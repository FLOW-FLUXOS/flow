"""
Cliente HTTP do microserviço de Pagamentos (usado pelas telas web).
O app Flutter chama o microserviço direto, pelo gateway, com o próprio token.
"""
import requests
from django.conf import settings

from .tokens import access_token_para


class PagamentosIndisponivel(Exception):
    pass


def _req(metodo, caminho, user, **kwargs):
    url = f"{settings.PAGAMENTOS_URL}/api/pagamentos/{caminho}"
    try:
        resp = requests.request(metodo, url, timeout=10,
                                headers={"Authorization": f"Bearer {access_token_para(user)}"}, **kwargs)
    except requests.RequestException as exc:
        raise PagamentosIndisponivel("Serviço de pagamentos fora do ar. Tente novamente em instantes.") from exc
    if resp.status_code >= 400:
        try:
            detalhe = resp.json().get("detail") or resp.text
        except ValueError:
            detalhe = resp.text
        raise PagamentosIndisponivel(f"Pagamentos respondeu {resp.status_code}: {detalhe}")
    return resp.json()


def listar_cobrancas(user):
    return _req("GET", "cobrancas/", user).get("results", [])


def criar_cobranca(user, plano, return_url=None):
    empresa = user.empresa
    dados = {"plano": plano, "cnpj": empresa.cnpj or "", "telefone": empresa.telefone or ""}
    if return_url:
        dados["return_url"] = return_url
    return _req("POST", "cobrancas/", user, json=dados)
