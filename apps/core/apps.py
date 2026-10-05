from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self):
        """
        Вызывается один раз при старте Django (runserver, gunicorn, celery).
        Инициализируем логирование здесь — до того как любой другой модуль
        попытается получить логгер.
        """
        from django.conf import settings
        if settings.GPG_DISABLE_LOGGING_INIT:
            return
        from logging_setup import init_logging
        init_logging(log_dir="logs", to_files=settings.GPG_LOG_TO_FILES)
