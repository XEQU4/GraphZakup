"""Offline Django tests: no dotenv, no production DB, Redis, or file logging."""

import os
from unittest.mock import patch

with patch.dict(os.environ, {
    "DJANGO_LOAD_DOTENV": "false",
    "SECRET_KEY": "offline-tests-only-key-never-use-in-deployment-0123456789",
    "GPG_DISABLE_LOGGING_INIT": "true",
}, clear=True):
    from .settings import *  # noqa: F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
GPG_DISABLE_LOGGING_INIT = True
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
ENABLE_SCHEDULED_IMPORT = False
CELERY_BEAT_SCHEDULE = {}
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
LOGGING_CONFIG = "logging.config.dictConfig"
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"null": {"class": "logging.NullHandler"}},
    "root": {"handlers": ["null"], "level": "WARNING"},
}
