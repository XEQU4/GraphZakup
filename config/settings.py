import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    value = os.getenv(name, str(default)).strip().lower()
    if value not in {"true", "false", "1", "0", "yes", "no"}:
        raise ImproperlyConfigured(f"{name} must be true or false.")
    return value in {"true", "1", "yes"}


def env_list(name, default=""):
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


if env_bool("DJANGO_LOAD_DOTENV", True):
    load_dotenv(BASE_DIR / ".env", override=False)

SECRET_KEY = os.getenv("SECRET_KEY", "").strip()
if not SECRET_KEY or SECRET_KEY == "replace-with-a-generated-secret":
    raise ImproperlyConfigured("Set a nonempty SECRET_KEY before starting Django.")
DEBUG = env_bool("DJANGO_DEBUG")
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
if not ALLOWED_HOSTS or (not DEBUG and "*" in ALLOWED_HOSTS):
    raise ImproperlyConfigured("ALLOWED_HOSTS must contain explicit hosts in production.")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

# English is the project baseline; Russian website localisation is planned later.
LANGUAGE_CODE = "en-us"

# Enable this only behind a proxy that replaces the incoming forwarded header.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if env_bool("TRUST_PROXY_SSL_HEADER") else None
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT")
SECURE_REDIRECT_EXEMPT = [r"^health/(live|ready)/$"]
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", SECURE_SSL_REDIRECT)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", SECURE_SSL_REDIRECT)
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS")
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD")
GPG_DISABLE_LOGGING_INIT = env_bool("GPG_DISABLE_LOGGING_INIT")
GPG_LOG_TO_FILES = env_bool("GPG_LOG_TO_FILES", True)


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",

    "django_celery_beat",

    "apps.companies.apps.CompaniesConfig",
    "apps.contracts.apps.ContractsConfig",
    "apps.owners.apps.OwnersConfig",
    "apps.graph.apps.GraphConfig",
    "apps.dashboard.apps.DashboardConfig",
    "apps.core.apps.CoreConfig",  # ← CoreConfig.ready() calls init_logging()
    "apps.ai.apps.AiConfig",
    "apps.ingestion.apps.IngestionConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

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
    }
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("PGDATABASE", os.getenv("DB_NAME")),
        "USER": os.getenv("PGUSER", os.getenv("DB_USER")),
        "PASSWORD": os.getenv("PGPASSWORD", os.getenv("DB_PASSWORD")),
        "HOST": os.getenv("PGHOST", os.getenv("DB_HOST")),
        "PORT": os.getenv("PGPORT", os.getenv("DB_PORT", "5432")),
        "CONN_MAX_AGE": 60,
        "OPTIONS": {"connect_timeout": 3},
    }
}

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# ─── CELERY ────────────────────────────────────────────────────────────────────
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "Asia/Almaty"
CELERY_ENABLE_UTC = True

ENABLE_SCHEDULED_IMPORT = env_bool("ENABLE_SCHEDULED_IMPORT")
CELERY_BEAT_SCHEDULE = {
    # Daily cleanup of logs older than 30 days
    "cleanup-logs-daily": {
        "task": "apps.core.tasks.cleanup_logs",
        "schedule": 60 * 60 * 24,
    },
}
if ENABLE_SCHEDULED_IMPORT:
    CELERY_BEAT_SCHEDULE["update-procurement-data"] = {
        "task": "apps.core.tasks.update_all_data",
        "schedule": 60 * 60 * 12,
    }
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_RESULT_EXPIRES = 60 * 60 * 24

# Applied by ingestion, shared by CLI and Celery. No live requests during offline tests.
INGESTION_LEASE_SECONDS = int(os.getenv('INGESTION_LEASE_SECONDS', '900'))
INGESTION_SOURCE_CACHE_SECONDS = int(os.getenv('INGESTION_SOURCE_CACHE_SECONDS', '900'))
INGESTION_REQUEST_INTERVAL = float(os.getenv('INGESTION_REQUEST_INTERVAL', '1.5'))

# ─── EXTERNAL APIs ───────────────────────────────────────────────────────────────
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "qwen/qwen3-8b:free")
GOSZAKUP_TOKEN = os.getenv("GOSZAKUP_TOKEN", "")

# Explicit opt-in; credentials are never stored in ingestion parameters/results.
ENABLE_KGD_CHECKS = env_bool("ENABLE_KGD_CHECKS")
KGD_PORTAL_TOKEN = os.getenv("KGD_PORTAL_TOKEN", "")
KGD_ACCOUNT_TOKENS_JSON = os.getenv("KGD_ACCOUNT_TOKENS_JSON", "{}")
KGD_TAXPAYER_TYPE = os.getenv("KGD_TAXPAYER_TYPE", "UL")
KGD_HTTP_TIMEOUT = int(os.getenv("KGD_HTTP_TIMEOUT", "30"))
KGD_SOURCE_CACHE_SECONDS = int(os.getenv("KGD_SOURCE_CACHE_SECONDS", "900"))
KGD_RESULT_MAX_AGE_DAYS = int(os.getenv("KGD_RESULT_MAX_AGE_DAYS", "7"))
if not 1 <= KGD_HTTP_TIMEOUT <= 60 or KGD_SOURCE_CACHE_SECONDS < 0 or KGD_RESULT_MAX_AGE_DAYS < 1:
    raise ImproperlyConfigured("Invalid KGD timeout, cache lifetime or result age.")

# ─── LOGGING ───────────────────────────────────────────────────────────────
# Logging is configured by logging_setup (CoreConfig.ready()),
# rather than Django's LOGGING dictionary, preserving colours, rotation,
# and the existing format.
# Django and Celery use the same root logger and need no separate
# configuration.
LOGGING_CONFIG = None  # Disable Django dictConfig and use init_logging
