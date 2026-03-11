from django.contrib import admin

from apps.stories.models import AppSetting, Story, StoryFolder, StoryFolderMembership, StoryView


class StoryFolderMembershipInline(admin.TabularInline):
    model = StoryFolderMembership
    extra = 0


@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "has_audio", "created_at")
    search_fields = ("title", "author", "reddit_url")
    list_filter = ("created_at",)
    readonly_fields = ("content_hash", "created_at", "updated_at")

    @admin.display(boolean=True)
    def has_audio(self, obj):
        return bool(obj.audio_file_path)


@admin.register(StoryView)
class StoryViewAdmin(admin.ModelAdmin):
    list_display = ("user", "story", "viewed_at", "hidden")
    list_filter = ("hidden",)


@admin.register(StoryFolder)
class StoryFolderAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "story_count", "created_at")
    inlines = [StoryFolderMembershipInline]

    @admin.display(description="Stories")
    def story_count(self, obj):
        return obj.stories.count()


@admin.register(AppSetting)
class AppSettingAdmin(admin.ModelAdmin):
    list_display = ("key", "short_value", "updated_at")

    @admin.display(description="Value")
    def short_value(self, obj):
        return obj.value[:80] + "..." if len(obj.value) > 80 else obj.value
