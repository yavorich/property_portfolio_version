from datetime import timedelta
from os import environ
from pathlib import Path
from corsheaders.defaults import default_headers
from telegram import Bot
from telegram.request import HTTPXRequest

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = environ["SECRET_KEY"]

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = environ.get("DEBUG", "1").lower() in ("true", "1")

ALLOWED_HOSTS = environ["ALLOWED_HOSTS"].split(",")

# Cors
CORS_ORIGIN_WHITELIST = environ["CORS_ORIGIN_WHITELIST"].split(",")

CSRF_TRUSTED_ORIGINS = environ["CORS_ORIGIN_WHITELIST"].split(",")

CORS_ALLOW_HEADERS = default_headers + (
    "Access-Control-Allow-Headers",
    "Access-Control-Allow-Credentials",
    "Access-Control-Allow-Origin",
)

CORS_ALLOW_CREDENTIALS = True

# https
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Application definition

LOCAL_APPS = [
    "apps.account",
    "apps.listings",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "corsheaders",
    "nested_admin",
    "adminsortable2",
    "django_celery_beat",
]

INSTALLED_APPS = (
    [
        "unfold",
        "unfold.contrib.filters",
        "unfold.contrib.forms",
        "unfold.contrib.inlines",
        "unfold.contrib.import_export",
        "unfold.contrib.guardian",
        "unfold.contrib.simple_history",
        "core.unfold_admin",
        "core.unfold_nested",
        # "core.unfold_autocomplete",
        "django.contrib.admin",
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.sessions",
        "django.contrib.messages",
        "django.contrib.staticfiles",
    ]
    + THIRD_PARTY_APPS
    + LOCAL_APPS
)

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

AUTH_USER_MODEL = "account.AdminUser"

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

ASGI_APPLICATION = "config.asgi.application"

# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": environ["POSTGRES_DB"],
        "USER": environ["POSTGRES_USER"],
        "PASSWORD": environ["POSTGRES_PASSWORD"],
        "HOST": environ["POSTGRES_HOST"],
        "PORT": environ["POSTGRES_PORT"],
        "ATOMIC_REQUESTS": True,
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": f'redis://{environ["REDIS_HOST"]}:{environ["REDIS_PORT"]}',
    }
}

RABBITMQ = {
    "PROTOCOL": "amqp",
    "HOST": environ["RABBITMQ_HOST"],
    "PORT": environ["RABBITMQ_PORT"],
    "USER": environ["RABBITMQ_USER"],
    "PASSWORD": environ["RABBITMQ_PASSWORD"],
}

CELERY_BROKER_URL = (
    f"{RABBITMQ['PROTOCOL']}://{RABBITMQ['USER']}"
    f":{RABBITMQ['PASSWORD']}@{RABBITMQ['HOST']}:{RABBITMQ['PORT']}"
)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_ENABLE_UTC = False
CELERY_MAX_TASKS_PER_CHILD = 1
CELERY_RESULT_BACKEND = "rpc://"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TASK_SERIALIZER = "json"

DJANGO_CELERY_BEAT_TZ_AWARE = True

# Password validation
AUTH_PASSWORD_VALIDATORS = []


# Internationalization

LANGUAGE_CODE = "ru"

TIME_ZONE = "Europe/Moscow"

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"
MEDIA_URL = "/media/"

STATIC_ROOT = BASE_DIR / "static"
MEDIA_ROOT = BASE_DIR / "media"

STATICFILES_DIRS = [
    BASE_DIR / "staticfiles",
]

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# rest framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.AllowAny",),
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=7),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": True,
    "TOKEN_REFRESH_SERIALIZER": "apps.account.serializers.TokenUserRefreshSerializer",
}

UNFOLD = {
    "SITE_TITLE": "Curl",
    "SITE_HEADER": "Администрирование",
    "SITE_URL": None,
    "SITE_SYMBOL": None,
    "SHOW_HISTORY": False,
    "SHOW_VIEW_ON_SITE": True,
}

TELEGRAM_BOT_TOKEN = environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_PROXY_URL = environ.get("TELEGRAM_PROXY_URL")
TELEGRAM_PROXY_FILE = environ.get("TELEGRAM_PROXY_FILE")

if TELEGRAM_BOT_TOKEN:
    _bot_request = HTTPXRequest(proxy=TELEGRAM_PROXY_URL) if TELEGRAM_PROXY_URL else None
    MAIN_BOT = Bot(TELEGRAM_BOT_TOKEN, request=_bot_request) if _bot_request else Bot(TELEGRAM_BOT_TOKEN)
else:
    MAIN_BOT = None

