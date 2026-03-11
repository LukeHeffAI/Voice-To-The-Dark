from django.contrib import admin

from apps.audio.models import Character, NarrationScript, ScriptSegment


class CharacterInline(admin.TabularInline):
    model = Character
    extra = 0


class ScriptSegmentInline(admin.TabularInline):
    model = ScriptSegment
    extra = 0
    fields = ("order", "type", "character", "text", "tone", "description", "duration_ms", "loop")


@admin.register(NarrationScript)
class NarrationScriptAdmin(admin.ModelAdmin):
    list_display = ("title", "story", "character_count", "segment_count", "created_at")
    inlines = [CharacterInline, ScriptSegmentInline]

    @admin.display(description="Characters")
    def character_count(self, obj):
        return obj.characters.count()

    @admin.display(description="Segments")
    def segment_count(self, obj):
        return obj.segments.count()


@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = ("name", "voice_profile", "voice_id", "script")
    search_fields = ("name",)


@admin.register(ScriptSegment)
class ScriptSegmentAdmin(admin.ModelAdmin):
    list_display = ("order", "type", "character", "script")
    list_filter = ("type",)
