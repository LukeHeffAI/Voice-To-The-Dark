from django.conf import settings
from django.db import models


class Story(models.Model):
    title = models.CharField(max_length=500)
    reddit_url = models.URLField(max_length=500, unique=True, null=True, blank=True, db_index=True)
    text_content = models.TextField()
    narration_text = models.TextField(blank=True, default="")
    content_hash = models.CharField(max_length=64, db_index=True)
    author = models.CharField(max_length=200, blank=True, default="")
    audio_file_path = models.CharField(max_length=500, blank=True, default="")
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
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="story_views"
    )
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name="views")
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
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="folders"
    )
    name = models.CharField(max_length=60)
    stories = models.ManyToManyField(
        Story, through="StoryFolderMembership", related_name="folders"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "story_folders"
        constraints = [
            models.UniqueConstraint(fields=["user", "name"], name="uq_user_folder_name"),
        ]

    def __str__(self):
        return f"{self.user}/{self.name}"


class StoryFolderMembership(models.Model):
    folder = models.ForeignKey(StoryFolder, on_delete=models.CASCADE)
    story = models.ForeignKey(Story, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "story_folder_memberships"
        constraints = [
            models.UniqueConstraint(fields=["folder", "story"], name="uq_folder_story"),
        ]


class AppSetting(models.Model):
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
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return default

    @classmethod
    def set(cls, key, value):
        cls.objects.update_or_create(key=key, defaults={"value": value})
