from django.contrib import admin

from apps.player.models import PlaybackState


@admin.register(PlaybackState)
class PlaybackStateAdmin(admin.ModelAdmin):
    list_display = ("user", "story", "position_seconds", "updated_at")
    list_filter = ("updated_at",)
