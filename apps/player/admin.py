from django.contrib import admin

from .models import PlaybackState


@admin.register(PlaybackState)
class PlaybackStateAdmin(admin.ModelAdmin):
    list_display = ["user", "story", "position_seconds", "updated_at"]
