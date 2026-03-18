"""Background task executor using ThreadPoolExecutor.

Single worker thread to avoid SQLite write contention. Tasks are submitted
via submit_task() and run in the background with lifecycle management.
"""

import logging
from concurrent.futures import ThreadPoolExecutor

from django.utils import timezone

logger = logging.getLogger(__name__)

# Single worker serialises tasks to avoid SQLite write contention
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bg-task")


def submit_task(task_id: int, func, *args, **kwargs):
    """Submit a background task for execution."""
    _executor.submit(_run_task, task_id, func, *args, **kwargs)


def _run_task(task_id: int, func, *args, **kwargs):
    """Wrapper that manages task lifecycle: processing → complete/failed."""
    from apps.tasks.models import BackgroundTask, TaskStatus

    try:
        task = BackgroundTask.objects.get(id=task_id)
        task.status = TaskStatus.PROCESSING
        task.started_at = timezone.now()
        task.save(update_fields=["status", "started_at"])

        result = func(task, *args, **kwargs)

        task.refresh_from_db()
        task.status = TaskStatus.COMPLETE
        task.completed_at = timezone.now()
        task.result_data = result
        task.save(update_fields=["status", "completed_at", "result_data"])

    except Exception as exc:
        logger.exception("Background task %d failed", task_id)
        try:
            task = BackgroundTask.objects.get(id=task_id)
            task.status = TaskStatus.FAILED
            task.error_message = str(exc)
            task.completed_at = timezone.now()
            task.save(update_fields=["status", "error_message", "completed_at"])
        except Exception:
            logger.exception("Failed to update task %d status", task_id)
