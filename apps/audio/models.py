from django.conf import settings
from django.db import models


class GenerationTask(models.Model):
    """Tracks background script/narration generation tasks with progress."""

    TASK_TYPES = [
        ("script", "Script Generation"),
        ("narration", "Narration Generation"),
    ]
    STATUSES = [
        ("queued", "Queued"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="generation_tasks",
    )
    story = models.ForeignKey(
        "stories.Story",
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    task_type = models.CharField(max_length=20, choices=TASK_TYPES)
    status = models.CharField(max_length=20, choices=STATUSES, default="queued")
    progress = models.IntegerField(default=0)
    stage = models.CharField(max_length=200, blank=True, default="")
    result_json = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "generation_tasks"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Task {self.id}: {self.task_type} for story {self.story_id} ({self.status})"
