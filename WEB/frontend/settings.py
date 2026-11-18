"""
FLOW Web — front-end separado.

Este projeto NÃO tem banco de dados nem models. Ele só entrega as telas
(HTML, CSS e JavaScript). Quem busca e grava os dados é o navegador,
chamando a API principal (/api/v1/) e a API de pagamentos (/api/pagamentos/)
com o token JWT do usuário — exatamente como o app Flutter.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR.parent / ".env")


def env_bool(nome, padrao=False):
    return os.getenv(nome, str(padrao)).strip().lower() in ("1", "true", "yes", "sim", "on")


SECRET_KEY = os.getenv("WEB_SECRET_KEY", "dev-insecure-web-troque-no-env")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [h.strip() for h in os.getenv(
    "WEB_ALLOWED_HOSTS", "127.0.0.1,localhost,frontend,10.0.2.2,.ngrok-free.app,.ngrok-free.dev").split(",") if h.strip()]

# Endereço das APIs visto pelo NAVEGADOR.
# Vazio = mesmo endereço do site (via gateway, no Docker).
# Rodando sem Docker:  FLOW_API_URL=http://127.0.0.1:8000  FLOW_PAGAMENTOS_URL=http://127.0.0.1:8001
FLOW_API_URL = os.getenv("FLOW_API_URL", "").rstrip("/")
FLOW_PAGAMENTOS_URL = os.getenv("FLOW_PAGAMENTOS_URL", "").rstrip("/")

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "frontend",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "frontend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "frontend.context_processors.config",
            ],
        },
    },
]

WSGI_APPLICATION = "frontend.wsgi.application"

# Sem banco de dados: o front não acessa dados diretamente.
DATABASES = {}

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
