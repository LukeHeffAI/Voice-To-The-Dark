from django.contrib import admin

from .models import AppSetting, Story, StoryFolder, StoryFolderMembership, StoryView


@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    list_display = ["title", "author", "part_count", "created_at", "has_script", "has_audio"]
    list_filter = ["part_count", "created_at"]
    search_fields = ["title", "author", "reddit_url"]
    readonly_fields = ["content_hash", "created_at", "updated_at"]

    @admin.display(boolean=True)
    def has_script(self, obj):
        return obj.script_json is not None

    @admin.display(boolean=True)
    def has_audio(self, obj):
        return bool(obj.audio_file_path)


@admin.register(StoryView)
class StoryViewAdmin(admin.ModelAdmin):
    list_display = ["user", "story", "viewed_at", "hidden"]
    list_filter = ["hidden"]


@admin.register(StoryFolder)
class StoryFolderAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "created_at"]


@admin.register(StoryFolderMembership)
class StoryFolderMembershipAdmin(admin.ModelAdmin):
    list_display = ["folder", "story", "added_at"]


@admin.register(AppSetting)
class AppSettingAdmin(admin.ModelAdmin):
    list_display = ["key", "value", "updated_at"]
