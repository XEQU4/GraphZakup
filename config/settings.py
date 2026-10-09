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
    "rest_framework",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    "apps.api.apps.ApiConfig",

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
BACKGROUND_INTERVAL_SECONDS = int(os.getenv('BACKGROUND_INTERVAL_SECONDS', '900'))
BACKGROUND_COMPANY_BATCH = int(os.getenv('BACKGROUND_COMPANY_BATCH', '5'))
BACKGROUND_CONTRACT_BATCH = int(os.getenv('BACKGROUND_CONTRACT_BATCH', '25'))
BACKGROUND_KGD_BATCH = int(os.getenv('BACKGROUND_KGD_BATCH', '2'))
BACKGROUND_MAX_REQUESTS = int(os.getenv('BACKGROUND_MAX_REQUESTS', '120'))
BACKGROUND_RETRY_SECONDS = int(os.getenv('BACKGROUND_RETRY_SECONDS', '21600'))
BACKGROUND_SOURCE_COOLDOWN_SECONDS = int(os.getenv('BACKGROUND_SOURCE_COOLDOWN_SECONDS', '3600'))
ENABLE_SCHEDULED_KGD = env_bool('ENABLE_SCHEDULED_KGD')
if (not 60 <= BACKGROUND_INTERVAL_SECONDS <= 86400 or not 1 <= BACKGROUND_COMPANY_BATCH <= 50
        or not 1 <= BACKGROUND_CONTRACT_BATCH <= 500 or not 1 <= BACKGROUND_KGD_BATCH <= 10
        or not 10 <= BACKGROUND_MAX_REQUESTS <= 500 or not 300 <= BACKGROUND_RETRY_SECONDS <= 604800
        or not 300 <= BACKGROUND_SOURCE_COOLDOWN_SECONDS <= 86400):
    raise ImproperlyConfigured('Invalid bounded background collection settings.')
CELERY_BEAT_SCHEDULE = {
    # Daily cleanup of logs older than 30 days
    "cleanup-logs-daily": {
        "task": "apps.core.tasks.cleanup_logs",
        "schedule": 60 * 60 * 24,
    },
}
if ENABLE_SCHEDULED_IMPORT:
    CELERY_BEAT_SCHEDULE["update-procurement-data"] = {
        "task": "apps.core.tasks.collect_background",
        "schedule": BACKGROUND_INTERVAL_SECONDS,
        "options": {"queue": "ingestion", "expires": BACKGROUND_INTERVAL_SECONDS},
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

# Explicit background generation only. Existing credentials never enable paid AI.
AI_PROVIDER = os.getenv('AI_PROVIDER', 'template').strip().lower()
AI_MODEL = os.getenv('AI_MODEL', '').strip()
AI_MODEL_REVISION = os.getenv('AI_MODEL_REVISION', '').strip()
AI_BASE_URL = os.getenv('AI_BASE_URL', '').strip()
AI_OLLAMA_BASE_URL = os.getenv('AI_OLLAMA_BASE_URL', 'http://127.0.0.1:11434').strip()
AI_API_KEY = os.getenv('AI_API_KEY', '').strip()
AI_ALLOW_PAID = env_bool('AI_ALLOW_PAID')
AI_EXPERIMENTAL_SCORING = env_bool('AI_EXPERIMENTAL_SCORING')
AI_TIMEOUT_SECONDS = int(os.getenv('AI_TIMEOUT_SECONDS', '90'))
AI_MAX_OUTPUT_TOKENS = int(os.getenv('AI_MAX_OUTPUT_TOKENS', '1024'))
AI_MAX_INPUT_CHARS = int(os.getenv('AI_MAX_INPUT_CHARS', '8000'))
AI_MAX_FINDINGS = int(os.getenv('AI_MAX_FINDINGS', '12'))
AI_CONTEXT_TOKENS = int(os.getenv('AI_CONTEXT_TOKENS', '4096'))
if (AI_PROVIDER not in {'template', 'ollama', 'openai', 'openrouter'}
        or len(AI_MODEL_REVISION) > 120
        or not 5 <= AI_TIMEOUT_SECONDS <= 180 or not 128 <= AI_MAX_OUTPUT_TOKENS <= 4096
        or not 3000 <= AI_MAX_INPUT_CHARS <= 32000 or not 1 <= AI_MAX_FINDINGS <= 30
        or not 2048 <= AI_CONTEXT_TOKENS <= 32768):
    raise ImproperlyConfigured('Invalid AI provider or request limits.')

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

# Versioned, same-origin JSON API. GET reads saved domain results only.
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework.authentication.SessionAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.AllowAny'],
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    'DEFAULT_PARSER_CLASSES': ['rest_framework.parsers.JSONParser'],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
    'EXCEPTION_HANDLER': 'apps.api.common.exception_handler',
    'DEFAULT_SCHEMA_CLASS': 'apps.api.schema.ApiAutoSchema',
    'DEFAULT_THROTTLE_RATES': {'api_login': '10/min', 'api_register': '5/hour',
        'api_account': '60/min', 'api_password': '10/hour'},
    'NUM_PROXIES': 0,
    'COERCE_DECIMAL_TO_STRING': True,
    'URL_FORMAT_OVERRIDE': None,
}
SPECTACULAR_SETTINGS = {
    'TITLE': 'IZ2 API',
    'DESCRIPTION': 'Saved procurement relationship evidence and versioned analysis. '
        'Public scores prioritise review; they are not probabilities of wrongdoing. '
        'Same-origin sessions and CSRF protect writes. Source collection is not launched by this API.',
    'VERSION': '1.0.0',
    'SCHEMA_PATH_PREFIX': r'/api/v1',
    'SCHEMA_PATH_PREFIX_TRIM': False,
    'SERVE_INCLUDE_SCHEMA': False,
    'SWAGGER_UI_DIST': 'SIDECAR',
    'SWAGGER_UI_FAVICON_HREF': 'SIDECAR',
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'filter': True,
        'docExpansion': 'none',
        'defaultModelsExpandDepth': 0,
        'displayRequestDuration': True,
        'persistAuthorization': False,
        'syntaxHighlight': {'activated': True, 'theme': 'nord'},
    },
    'SERVE_AUTHENTICATION': [],
    'SERVE_PERMISSIONS': ['rest_framework.permissions.AllowAny'],
    'COMPONENT_SPLIT_REQUEST': True,
    'ENUM_NAME_OVERRIDES': {
        'AnalysisStatusEnum': ['not_calculated', 'ready', 'stale'],
        'KgdCoverageStatusEnum': ['not_assessed', 'no_checks', 'partial', 'checked'],
    },
}

# Apply password checks to signup and explicit password changes; existing logins remain compatible.
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
