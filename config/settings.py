import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY")
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")

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
    "apps.core.apps.CoreConfig",  # ← CoreConfig.ready() вызывает init_logging()
    "apps.ai.apps.AiConfig",
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
    }
}

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

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

CELERY_BEAT_SCHEDULE = {
    # Каждые 12 часов — парсинг 500 новых контрактов
    "update-procurement-data": {
        "task": "apps.core.tasks.update_all_data",
        "schedule": 60 * 60 * 12,
    },
    # Раз в сутки — очистка логов старше 30 дней
    "cleanup-logs-daily": {
        "task": "apps.core.tasks.cleanup_logs",
        "schedule": 60 * 60 * 24,
    },
}

# ─── ВНЕШНИЕ API ───────────────────────────────────────────────────────────────
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = "qwen/qwen3-8b:free"
GOSZAKUP_TOKEN = os.getenv("GOSZAKUP_TOKEN", "")

# ─── ЛОГИРОВАНИЕ ───────────────────────────────────────────────────────────────
# Логирование настраивается через logging_setup (CoreConfig.ready()),
# а не через Django LOGGING dict — чтобы сохранить цвета, ротацию файлов
# и формат из твоего шаблона.
# Django и Celery пишут через тот же root logger, поэтому настраивать
# их отдельно не нужно.
LOGGING_CONFIG = None  # отключаем Django's dictConfig, используем свой init_logging
