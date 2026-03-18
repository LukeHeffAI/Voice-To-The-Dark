import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class TasksConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tasks"

    def ready(self):
        """Schedule orphaned task cleanup for after Django is fully ready."""
        from django.db.models.signals import post_migrate

        post_migrate.connect(_cleanup_orphaned_tasks, sender=self)


def _cleanup_orphaned_tasks(sender, **kwargs):
    """Mark orphaned processing and queued tasks as failed on server startup."""
    from apps.tasks.models import ACTIVE_STATUSES, BackgroundTask

    try:
        # Tasks that were actively processing when the server restarted.
        processing_count = BackgroundTask.objects.filter(
            status__in=[s.value for s in ACTIVE_STATUSES],
            started_at__isnull=False,
        ).update(
            status="failed",
            error_message="Server restarted during processing",
        )

        # Tasks that were queued but never started processing before restart.
        queued_count = BackgroundTask.objects.filter(
            status="queued",
            started_at__isnull=True,
        ).update(
            status="failed",
            error_message="Server restarted before task started processing",
        )

        total_failed = (processing_count or 0) + (queued_count or 0)
        if total_failed:
            logger.info("Marked %d orphaned tasks as failed", total_failed)
    except Exception:
        pass
