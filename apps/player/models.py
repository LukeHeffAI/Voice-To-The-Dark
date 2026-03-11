from django.conf import settings
from django.db import models


class PlaybackState(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="playback_states"
    )
    story = models.ForeignKey(
        "stories.Story", on_delete=models.CASCADE, related_name="playback_states"
    )
    position_seconds = models.FloatField(default=0.0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "playback_states"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "story"], name="uq_user_story_playback"
            ),
        ]

    def __str__(self):
        return f"{self.user} @ {self.position_seconds}s in {self.story}"
