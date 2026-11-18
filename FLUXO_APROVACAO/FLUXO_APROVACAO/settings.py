"""
Django settings for FLUXO_APROVACAO project (FLOW).

Toda configuração sensível vem de variáveis de ambiente (.env).
Veja o arquivo .env.example na raiz do repositório.
"""

import os
from datetime import timedelta
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


# ----------------------------------------------------------
# Segurança
# ----------------------------------------------------------
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-troque-esta-chave-no-env")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost,10.0.2.2,.ngrok-free.dev")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "")

# ----------------------------------------------------------
# Integrações
# ----------------------------------------------------------
# URL pública do sistema (links de retorno do checkout)
SITE_URL = os.getenv("SITE_URL", "http://127.0.0.1:8000")
# Caminho do JSON da conta de serviço do Firebase (opcional, para push no celular)
FIREBASE_CREDENTIALS = os.getenv("FIREBASE_CREDENTIALS")

# ----------------------------------------------------------
# Apps
# ----------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # terceiros
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'django_filters',
    'corsheaders',
    'drf_spectacular',
    # projeto
    'SISTEMA.apps.SistemaConfig',
    'api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'FLUXO_APROVACAO.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'FLUXO_APROVACAO.wsgi.application'

# ----------------------------------------------------------
# Banco de dados
# DATABASE_URL=postgres://user:senha@db:5432/flow  (Docker)
# sem DATABASE_URL -> SQLite local (desenvolvimento)
# ----------------------------------------------------------
DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{os.getenv('SQLITE_PATH', BASE_DIR / 'db.sqlite3')}",
        conn_max_age=600,
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

# As telas ficam no projeto WEB (front separado). Aqui só há estáticos do /admin e do Swagger.
STATIC_URL = '/api-static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'SISTEMA.Usuario'

# ----------------------------------------------------------
# API REST (Django REST Framework + JWT)
# ----------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',  # Swagger quando logado no /admin
    ),
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAuthenticated',),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'api.pagination.Paginacao',
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=int(os.getenv('JWT_ACCESS_MINUTES', '60'))),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=int(os.getenv('JWT_REFRESH_DAYS', '7'))),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    # chave compartilhada com o microserviço de pagamentos (ele valida os mesmos tokens)
    'SIGNING_KEY': os.getenv('JWT_SIGNING_KEY', 'dev-jwt-chave-compartilhada-troque-no-env'),
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'FLOW API',
    'DESCRIPTION': 'API do FLOW — Fluxo de Aprovação Sequencial (mobile Flutter + web).',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'ENUM_NAME_OVERRIDES': {'PerfilEnum': 'SISTEMA.models.PERFIL_CHOICES'},
}

# CORS (Flutter Web / outros fronts)
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "")
CORS_ALLOW_ALL_ORIGINS = env_bool("CORS_ALLOW_ALL_ORIGINS", DEBUG)
CORS_URLS_REGEX = r"^/api/.*$"

# ----------------------------------------------------------
# Mensageria (Celery + RabbitMQ)
# CELERY_BROKER_URL=amqp://flow:flow@rabbitmq:5672//
# Sem broker configurado, as tarefas rodam na hora (modo síncrono),
# assim dá pra desenvolver sem subir o RabbitMQ.
# ----------------------------------------------------------
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "")
# Conexão usada pelo consumidor de eventos de pagamento (exchange "pagamentos")
RABBITMQ_URL = os.getenv("RABBITMQ_URL") or CELERY_BROKER_URL or "memory://"
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", not CELERY_BROKER_URL)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_RESULT_BACKEND = None
CELERY_TASK_IGNORE_RESULT = True
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_ROUTES = {
    "SISTEMA.tasks.processar_evento_fluxo": {"queue": "fluxo.eventos"},
    "SISTEMA.tasks.enviar_push": {"queue": "notificacoes.push"},
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"SISTEMA": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")}},
}

if not DEBUG:
    SESSION_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", False)
    CSRF_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", False)
