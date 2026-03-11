from django.db import models


class SegmentType(models.TextChoices):
    NARRATION = "narration", "Narration"
    DIALOGUE = "dialogue", "Dialogue"
    SFX = "sfx", "Sound Effect"
    AMBIENT = "ambient", "Ambient"
    PAUSE = "pause", "Pause"


class NarrationScript(models.Model):
    story = models.OneToOneField(
        "stories.Story", on_delete=models.CASCADE, related_name="script"
    )
    title = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "narration_scripts"

    def __str__(self):
        return f"Script: {self.title}"


class Character(models.Model):
    script = models.ForeignKey(
        NarrationScript, on_delete=models.CASCADE, related_name="characters"
    )
    name = models.CharField(max_length=100)
    voice_profile = models.TextField()
    voice_id = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        db_table = "characters"
        constraints = [
            models.UniqueConstraint(
                fields=["script", "name"], name="uq_script_character_name"
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.script.title})"


class ScriptSegment(models.Model):
    script = models.ForeignKey(
        NarrationScript, on_delete=models.CASCADE, related_name="segments"
    )
    order = models.PositiveIntegerField()
    type = models.CharField(max_length=20, choices=SegmentType.choices)
    character = models.ForeignKey(
        Character, null=True, blank=True, on_delete=models.SET_NULL
    )
    text = models.TextField(blank=True, default="")
    tone = models.CharField(max_length=100, blank=True, default="")
    description = models.TextField(blank=True, default="")
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    loop = models.BooleanField(default=False)

    class Meta:
        db_table = "script_segments"
        ordering = ["order"]

    def __str__(self):
        return f"Segment {self.order}: {self.type}"
