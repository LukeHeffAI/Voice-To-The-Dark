"""Tests for the new Django models (Phase 2)."""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django  # noqa: E402

django.setup()

import pytest  # noqa: E402
from django.db import IntegrityError  # noqa: E402
from django.test import TestCase  # noqa: E402

from apps.accounts.models import User  # noqa: E402
from apps.audio.models import Character, NarrationScript, ScriptSegment, SegmentType  # noqa: E402
from apps.player.models import PlaybackState  # noqa: E402
from apps.stories.models import AppSetting, Story, StoryFolder, StoryFolderMembership, StoryView  # noqa: E402


class StoryModelTests(TestCase):
    def test_create_story(self):
        story = Story.objects.create(
            title="The Haunted House",
            text_content="Once upon a time...",
            content_hash="abc123",
        )
        assert story.pk is not None
        assert story.title == "The Haunted House"
        assert story.part_count == 1
        assert story.series_json is None

    def test_story_with_reddit_url(self):
        story = Story.objects.create(
            title="Test Story",
            reddit_url="https://reddit.com/r/nosleep/comments/abc/test/",
            text_content="Content here",
            content_hash="def456",
        )
        assert story.reddit_url == "https://reddit.com/r/nosleep/comments/abc/test/"

    def test_story_unique_reddit_url(self):
        Story.objects.create(
            title="Story 1",
            reddit_url="https://reddit.com/r/nosleep/comments/abc/test/",
            text_content="Content",
            content_hash="hash1",
        )
        with pytest.raises(IntegrityError):
            Story.objects.create(
                title="Story 2",
                reddit_url="https://reddit.com/r/nosleep/comments/abc/test/",
                text_content="Other content",
                content_hash="hash2",
            )

    def test_story_null_reddit_url_allowed(self):
        s1 = Story.objects.create(title="S1", text_content="C1", content_hash="h1")
        s2 = Story.objects.create(title="S2", text_content="C2", content_hash="h2")
        assert s1.reddit_url is None
        assert s2.reddit_url is None

    def test_story_series_json(self):
        series_data = [
            {"title": "Part 1", "url": "https://reddit.com/1", "part_number": 1},
            {"title": "Part 2", "url": "https://reddit.com/2", "part_number": 2},
        ]
        story = Story.objects.create(
            title="Series Story",
            text_content="Content",
            content_hash="hash1",
            series_json=series_data,
        )
        story.refresh_from_db()
        assert story.series_json == series_data
        assert len(story.series_json) == 2

    def test_story_ordering(self):
        Story.objects.create(title="First", text_content="C", content_hash="h1")
        Story.objects.create(title="Second", text_content="C", content_hash="h2")
        stories = list(Story.objects.all())
        assert stories[0].title == "Second"  # newest first

    def test_story_str(self):
        story = Story.objects.create(title="My Story", text_content="C", content_hash="h")
        assert str(story) == "My Story"


class NarrationScriptModelTests(TestCase):
    def setUp(self):
        self.story = Story.objects.create(
            title="Test Story", text_content="Content", content_hash="hash1"
        )

    def test_create_script(self):
        script = NarrationScript.objects.create(story=self.story, title="Test Script")
        assert script.pk is not None
        assert script.story == self.story
        assert script.title == "Test Script"

    def test_one_to_one_with_story(self):
        NarrationScript.objects.create(story=self.story, title="Script 1")
        with pytest.raises(IntegrityError):
            NarrationScript.objects.create(story=self.story, title="Script 2")

    def test_cascade_delete_from_story(self):
        script = NarrationScript.objects.create(story=self.story, title="Script")
        Character.objects.create(script=script, name="narrator", voice_profile="deep voice")
        ScriptSegment.objects.create(
            script=script, order=0, type=SegmentType.NARRATION, text="Hello"
        )
        self.story.delete()
        assert NarrationScript.objects.count() == 0
        assert Character.objects.count() == 0
        assert ScriptSegment.objects.count() == 0

    def test_access_script_from_story(self):
        NarrationScript.objects.create(story=self.story, title="My Script")
        assert self.story.script.title == "My Script"


class CharacterModelTests(TestCase):
    def setUp(self):
        story = Story.objects.create(title="S", text_content="C", content_hash="h")
        self.script = NarrationScript.objects.create(story=story, title="Script")

    def test_create_character(self):
        char = Character.objects.create(
            script=self.script, name="narrator", voice_profile="deep, steady"
        )
        assert char.pk is not None
        assert char.voice_id == ""

    def test_character_with_voice_id(self):
        char = Character.objects.create(
            script=self.script,
            name="narrator",
            voice_profile="deep voice",
            voice_id="pNInz6obpgDQGcFmaJgB",
        )
        assert char.voice_id == "pNInz6obpgDQGcFmaJgB"

    def test_unique_name_per_script(self):
        Character.objects.create(
            script=self.script, name="narrator", voice_profile="voice 1"
        )
        with pytest.raises(IntegrityError):
            Character.objects.create(
                script=self.script, name="narrator", voice_profile="voice 2"
            )

    def test_same_name_different_scripts(self):
        story2 = Story.objects.create(title="S2", text_content="C", content_hash="h2")
        script2 = NarrationScript.objects.create(story=story2, title="Script 2")
        Character.objects.create(
            script=self.script, name="narrator", voice_profile="voice 1"
        )
        Character.objects.create(
            script=script2, name="narrator", voice_profile="voice 2"
        )
        assert Character.objects.filter(name="narrator").count() == 2


class ScriptSegmentModelTests(TestCase):
    def setUp(self):
        story = Story.objects.create(title="S", text_content="C", content_hash="h")
        self.script = NarrationScript.objects.create(story=story, title="Script")
        self.narrator = Character.objects.create(
            script=self.script, name="narrator", voice_profile="deep voice"
        )

    def test_create_narration_segment(self):
        seg = ScriptSegment.objects.create(
            script=self.script,
            order=0,
            type=SegmentType.NARRATION,
            character=self.narrator,
            text="I walked into the house.",
            tone="foreboding",
        )
        assert seg.pk is not None
        assert seg.character == self.narrator

    def test_create_sfx_segment(self):
        seg = ScriptSegment.objects.create(
            script=self.script,
            order=1,
            type=SegmentType.SFX,
            description="door creaking slowly",
        )
        assert seg.character is None
        assert seg.description == "door creaking slowly"

    def test_create_pause_segment(self):
        seg = ScriptSegment.objects.create(
            script=self.script,
            order=2,
            type=SegmentType.PAUSE,
            duration_ms=1500,
        )
        assert seg.duration_ms == 1500

    def test_create_ambient_segment(self):
        seg = ScriptSegment.objects.create(
            script=self.script,
            order=0,
            type=SegmentType.AMBIENT,
            description="rain on windows",
            loop=True,
        )
        assert seg.loop is True

    def test_segment_ordering(self):
        ScriptSegment.objects.create(script=self.script, order=2, type=SegmentType.PAUSE, duration_ms=500)
        ScriptSegment.objects.create(
            script=self.script, order=0, type=SegmentType.NARRATION, text="First"
        )
        ScriptSegment.objects.create(script=self.script, order=1, type=SegmentType.SFX, description="bang")
        segments = list(self.script.segments.all())
        assert [s.order for s in segments] == [0, 1, 2]

    def test_character_set_null_on_delete(self):
        seg = ScriptSegment.objects.create(
            script=self.script,
            order=0,
            type=SegmentType.DIALOGUE,
            character=self.narrator,
            text="Hello",
        )
        self.narrator.delete()
        seg.refresh_from_db()
        assert seg.character is None

    def test_segment_type_choices(self):
        assert SegmentType.NARRATION == "narration"
        assert SegmentType.DIALOGUE == "dialogue"
        assert SegmentType.SFX == "sfx"
        assert SegmentType.AMBIENT == "ambient"
        assert SegmentType.PAUSE == "pause"


class PlaybackStateModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="pass123")
        self.story = Story.objects.create(title="S", text_content="C", content_hash="h")

    def test_create_playback_state(self):
        state = PlaybackState.objects.create(
            user=self.user, story=self.story, position_seconds=42.5
        )
        assert state.pk is not None
        assert state.position_seconds == 42.5

    def test_default_position(self):
        state = PlaybackState.objects.create(user=self.user, story=self.story)
        assert state.position_seconds == 0.0

    def test_unique_user_story(self):
        PlaybackState.objects.create(user=self.user, story=self.story, position_seconds=10.0)
        with pytest.raises(IntegrityError):
            PlaybackState.objects.create(user=self.user, story=self.story, position_seconds=20.0)

    def test_update_position(self):
        state = PlaybackState.objects.create(user=self.user, story=self.story, position_seconds=10.0)
        state.position_seconds = 55.3
        state.save()
        state.refresh_from_db()
        assert state.position_seconds == 55.3

    def test_cascade_delete_user(self):
        PlaybackState.objects.create(user=self.user, story=self.story)
        self.user.delete()
        assert PlaybackState.objects.count() == 0

    def test_cascade_delete_story(self):
        PlaybackState.objects.create(user=self.user, story=self.story)
        self.story.delete()
        assert PlaybackState.objects.count() == 0


class StoryViewModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="pass123")
        self.story = Story.objects.create(title="S", text_content="C", content_hash="h")

    def test_create_story_view(self):
        view = StoryView.objects.create(user=self.user, story=self.story)
        assert view.pk is not None
        assert view.hidden is False

    def test_unique_user_story(self):
        StoryView.objects.create(user=self.user, story=self.story)
        with pytest.raises(IntegrityError):
            StoryView.objects.create(user=self.user, story=self.story)

    def test_hidden_flag(self):
        view = StoryView.objects.create(user=self.user, story=self.story, hidden=True)
        assert view.hidden is True


class StoryFolderModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="pass123")
        self.story1 = Story.objects.create(title="S1", text_content="C", content_hash="h1")
        self.story2 = Story.objects.create(title="S2", text_content="C", content_hash="h2")

    def test_create_folder(self):
        folder = StoryFolder.objects.create(user=self.user, name="Favorites")
        assert folder.pk is not None
        assert folder.name == "Favorites"

    def test_unique_name_per_user(self):
        StoryFolder.objects.create(user=self.user, name="Favorites")
        with pytest.raises(IntegrityError):
            StoryFolder.objects.create(user=self.user, name="Favorites")

    def test_same_name_different_users(self):
        user2 = User.objects.create_user(username="user2", password="pass")
        StoryFolder.objects.create(user=self.user, name="Favorites")
        StoryFolder.objects.create(user=user2, name="Favorites")
        assert StoryFolder.objects.filter(name="Favorites").count() == 2

    def test_add_story_to_folder(self):
        folder = StoryFolder.objects.create(user=self.user, name="Favorites")
        StoryFolderMembership.objects.create(folder=folder, story=self.story1)
        StoryFolderMembership.objects.create(folder=folder, story=self.story2)
        assert folder.stories.count() == 2

    def test_unique_story_per_folder(self):
        folder = StoryFolder.objects.create(user=self.user, name="Favorites")
        StoryFolderMembership.objects.create(folder=folder, story=self.story1)
        with pytest.raises(IntegrityError):
            StoryFolderMembership.objects.create(folder=folder, story=self.story1)

    def test_cascade_delete_folder(self):
        folder = StoryFolder.objects.create(user=self.user, name="Favorites")
        StoryFolderMembership.objects.create(folder=folder, story=self.story1)
        folder.delete()
        assert StoryFolderMembership.objects.count() == 0
        # Story should still exist
        assert Story.objects.filter(pk=self.story1.pk).exists()

    def test_cascade_delete_user(self):
        folder = StoryFolder.objects.create(user=self.user, name="Favorites")
        StoryFolderMembership.objects.create(folder=folder, story=self.story1)
        self.user.delete()
        assert StoryFolder.objects.count() == 0
        assert StoryFolderMembership.objects.count() == 0


class AppSettingModelTests(TestCase):
    def test_get_nonexistent_returns_default(self):
        assert AppSetting.get("missing_key") == ""
        assert AppSetting.get("missing_key", "fallback") == "fallback"

    def test_set_and_get(self):
        AppSetting.set("cache_ttl", "3600")
        assert AppSetting.get("cache_ttl") == "3600"

    def test_set_overwrites(self):
        AppSetting.set("cache_ttl", "3600")
        AppSetting.set("cache_ttl", "7200")
        assert AppSetting.get("cache_ttl") == "7200"
        assert AppSetting.objects.count() == 1

    def test_str(self):
        AppSetting.set("key", "value")
        setting = AppSetting.objects.get(key="key")
        assert str(setting) == "key=value"
