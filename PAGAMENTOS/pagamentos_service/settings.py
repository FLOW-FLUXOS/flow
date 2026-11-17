"""
FLOW Pagamentos — microserviço responsável por cobranças e pagamentos.

Banco próprio, API própria. Conversa com o resto do sistema por:
  - JWT emitido pela API principal (mesma chave de assinatura, sem consultar usuários)
  - Eventos no RabbitMQ (exchange "pagamentos", routing key "pagamento.<status>")
"""
import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR.parent / ".env")


def env_bool(nome, padrao=False):
    return os.getenv(nome, str(padrao)).strip().lower() in ("1", "true", "yes", "sim", "on")


def env_list(nome, padrao=""):
    return [v.strip() for v in os.getenv(nome, padrao).split(",") if v.strip()]


SECRET_KEY = os.getenv("PAGAMENTOS_SECRET_KEY", "dev-insecure-pagamentos-troque-no-env")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("PAGAMENTOS_ALLOWED_HOSTS", "127.0.0.1,localhost,pagamentos,10.0.2.2,.ngrok-free.dev")

# URL pública por onde o cliente acessa este serviço (via gateway)
PUBLIC_URL = os.getenv("PAGAMENTOS_PUBLIC_URL", "http://127.0.0.1:8001").rstrip("/")

# AbacatePay — sem chave, o serviço usa o SIMULADOR de pagamento
ABACATEPAY_API_KEY = os.getenv("ABACATEPAY_API_KEY")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
SIMULADOR_ATIVO = env_bool("SIMULADOR_PAGAMENTO", not ABACATEPAY_API_KEY)

# RabbitMQ
RABBITMQ_URL = os.getenv("RABBITMQ_URL") or os.getenv("CELERY_BROKER_URL") or "memory://"
EXCHANGE_PAGAMENTOS = "pagamentos"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    "cobrancas",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "pagamentos_service.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "pagamentos_service.wsgi.application"

DATABASES = {
    "default": dj_database_url.config(
        env="PAGAMENTOS_DATABASE_URL",
        default=f"sqlite:///{os.getenv('PAGAMENTOS_SQLITE_PATH', BASE_DIR / 'db_pagamentos.sqlite3')}",
        conn_max_age=600,
    )
}

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "api/pagamentos/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ----------------------------------------------------------
# Autenticação: valida o JWT da API principal SEM banco de usuários
# (JWTStatelessUserAuthentication lê empresa_id, perfil, email... do token)
# ----------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTStatelessUserAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "UNAUTHENTICATED_USER": None,
}

SIMPLE_JWT = {
    # mesma chave usada pela API principal para assinar os tokens
    "SIGNING_KEY": os.getenv("JWT_SIGNING_KEY", "dev-jwt-chave-compartilhada-troque-no-env"),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "FLOW Pagamentos API",
    "DESCRIPTION": "Microserviço de cobranças do FLOW. Cada mudança de status publica um evento no RabbitMQ.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

CORS_ALLOW_ALL_ORIGINS = env_bool("CORS_ALLOW_ALL_ORIGINS", DEBUG)
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "")

# ----------------------------------------------------------
# E-mail (no Docker: Mailpit em http://localhost:8025)
# ----------------------------------------------------------
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_BACKEND = (
    "django.core.mail.backends.smtp.EmailBackend" if EMAIL_HOST
    else "django.core.mail.backends.console.EmailBackend"
)
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "1025"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", False)
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "FLOW <nao-responda@flow.local>")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"cobrancas": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")}},
}
