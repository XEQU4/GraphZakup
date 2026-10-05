import logging

from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from redis import Redis

logger = logging.getLogger(__name__)


@require_GET
def health_live(request):
    return JsonResponse({"status": "ok"})


@require_GET
def health_ready(request):
    checks = {"database": False, "broker": False}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            checks["database"] = cursor.fetchone() == (1,)
    except Exception:
        logger.warning("Readiness database check failed")
    try:
        with Redis.from_url(settings.CELERY_BROKER_URL, socket_connect_timeout=2, socket_timeout=2) as client:
            checks["broker"] = bool(client.ping())
    except Exception:
        logger.warning("Readiness broker check failed")
    ready = all(checks.values())
    return JsonResponse({"status": "ok" if ready else "unavailable", "checks": checks}, status=200 if ready else 503)
