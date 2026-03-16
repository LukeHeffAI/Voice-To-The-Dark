from django.conf import settings
from django.db import models


class Story(models.Model):
    title = models.CharField(max_length=500)
    reddit_url = models.URLField(max_length=2000, unique=True, null=True, blank=True)
    text_content = models.TextField()
    narration_text = models.TextField(null=True, blank=True)
    script_json = models.JSONField(null=True, blank=True)
    content_hash = models.CharField(max_length=64, db_index=True)
    author = models.CharField(max_length=200, null=True, blank=True)
    audio_file_path = models.CharField(max_length=500, null=True, blank=True)
    part_count = models.PositiveIntegerField(default=1)
    series_json = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "stories"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class StoryView(models.Model):
    """Tracks when a user views a story, powering the 'Recently Viewed' home page."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="story_views",
    )
    story = models.ForeignKey(
        Story,
        on_delete=models.CASCADE,
        related_name="views",
    )
    viewed_at = models.DateTimeField(auto_now=True)
    hidden = models.BooleanField(default=False)

    class Meta:
        db_table = "story_views"
        constraints = [
            models.UniqueConstraint(fields=["user", "story"], name="uq_user_story_view"),
        ]

    def __str__(self):
        return f"{self.user} viewed {self.story}"


class StoryFolder(models.Model):
    """User-created folders for organising stories."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="folders",
    )
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "story_folders"
        constraints = [
            models.UniqueConstraint(fields=["user", "name"], name="uq_user_folder_name"),
        ]

    def __str__(self):
        return f"{self.user}: {self.name}"


class StoryFolderMembership(models.Model):
    """Junction table linking stories to folders."""

    folder = models.ForeignKey(
        StoryFolder,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    story = models.ForeignKey(
        Story,
        on_delete=models.CASCADE,
        related_name="folder_memberships",
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "story_folder_memberships"
        constraints = [
            models.UniqueConstraint(fields=["folder", "story"], name="uq_folder_story"),
        ]


class AppSetting(models.Model):
    """Key-value store for application settings."""

    key = models.CharField(max_length=200, primary_key=True)
    value = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "app_settings"

    def __str__(self):
        return f"{self.key}={self.value[:50]}"

    @classmethod
    def get(cls, key, default=""):
        try:
            return cls.objects.get(pk=key).value
        except cls.DoesNotExist:
            return default

    @classmethod
    def set(cls, key, value):
        cls.objects.update_or_create(pk=key, defaults={"value": value})
