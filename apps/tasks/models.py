from django.conf import settings
from django.db import models


class TaskStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    PROCESSING = "processing", "Processing"
    GENERATING_SEGMENTS = "generating_segments", "Generating Segments"
    MIXING = "mixing", "Mixing"
    COMPLETE = "complete", "Complete"
    FAILED = "failed", "Failed"


class TaskType(models.TextChoices):
    GENERATE_SCRIPT = "generate_script", "Generate Script"
    GENERATE_NARRATION = "generate_narration", "Generate Narration"


ACTIVE_STATUSES = [
    TaskStatus.QUEUED,
    TaskStatus.PROCESSING,
    TaskStatus.GENERATING_SEGMENTS,
    TaskStatus.MIXING,
]


class BackgroundTask(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tasks"
    )
    story = models.ForeignKey(
        "stories.Story", on_delete=models.CASCADE, related_name="tasks"
    )
    task_type = models.CharField(max_length=30, choices=TaskType.choices)
    status = models.CharField(
        max_length=30, choices=TaskStatus.choices, default=TaskStatus.QUEUED
    )
    # Progress tracking
    progress_current = models.PositiveIntegerField(default=0)
    progress_total = models.PositiveIntegerField(default=0)
    progress_message = models.CharField(max_length=500, blank=True, default="")
    # Result / error
    result_data = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "background_tasks"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["story", "task_type"],
                condition=models.Q(status__in=[s.value for s in ACTIVE_STATUSES]),
                name="uq_active_task_per_story_type",
            )
        ]

    def __str__(self):
        return f"Task {self.id}: {self.task_type} for story {self.story_id} ({self.status})"
