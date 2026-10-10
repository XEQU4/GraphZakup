"""Database scheduler with a local progress signal for container health checks."""

from django_celery_beat.schedulers import DatabaseScheduler

from config.container_health import BEAT_HEARTBEAT


class HealthyDatabaseScheduler(DatabaseScheduler):
    def tick(self, *args, **kwargs):
        interval = super().tick(*args, **kwargs)
        # Written only after a completed scheduler turn, never by the probe.
        # This measures scheduler progress, not successful source collection.
        BEAT_HEARTBEAT.touch()
        return interval
