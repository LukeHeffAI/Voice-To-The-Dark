"""Task status polling API endpoints."""

from ninja import Router, Schema
from ninja.errors import HttpError

from apps.accounts.auth import get_current_user
from apps.tasks.models import ACTIVE_STATUSES, BackgroundTask

router = Router()


class TaskStatusResponse(Schema):
    task_id: int
    task_type: str
    status: str
    progress_current: int
    progress_total: int
    progress_message: str
    result_data: dict | None = None
    error_message: str = ""
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None


def _task_to_response(task: BackgroundTask) -> dict:
    return {
        "task_id": task.id,
        "task_type": task.task_type,
        "status": task.status,
        "progress_current": task.progress_current,
        "progress_total": task.progress_total,
        "progress_message": task.progress_message,
        "result_data": task.result_data,
        "error_message": task.error_message,
        "created_at": task.created_at.isoformat(),
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


@router.get("/status/{task_id}", response=TaskStatusResponse)
def get_task_status(request, task_id: int):
    """Get the current status of a background task."""
    user = get_current_user(request)
    task = BackgroundTask.objects.filter(id=task_id, user=user).first()
    if not task:
        raise HttpError(404, "Task not found")
    return _task_to_response(task)


@router.get("/story/{story_id}", response=list[TaskStatusResponse])
def get_story_tasks(request, story_id: int):
    """Get active tasks for a story (for resuming polls on page reload)."""
    user = get_current_user(request)
    tasks = BackgroundTask.objects.filter(
        story_id=story_id,
        user=user,
        status__in=[s.value for s in ACTIVE_STATUSES],
    )
    return [_task_to_response(t) for t in tasks]
