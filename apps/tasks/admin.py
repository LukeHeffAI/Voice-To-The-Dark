from django.contrib import admin

from apps.tasks.models import BackgroundTask


@admin.register(BackgroundTask)
class BackgroundTaskAdmin(admin.ModelAdmin):
    list_display = ["id", "task_type", "status", "story", "user", "created_at", "completed_at"]
    list_filter = ["task_type", "status"]
    readonly_fields = ["result_data", "error_message"]
