"""Tests for audio API endpoints."""

import json
from unittest.mock import MagicMock, patch

import pytest

from apps.audio.helpers import pydantic_to_script, script_to_pydantic
from apps.audio.models import Character, NarrationScript as NarrationScriptModel
from apps.stories.models import Story
from apps.tasks.models import BackgroundTask, TaskType
from schemas.narration import CharacterProfile, NarrationScript, ScriptSegment, SegmentType


pytestmark = pytest.mark.django_db


@pytest.fixture
def story_with_script(test_story):
    """Create a story with a relational script."""
    script = NarrationScript(
        title="Test Script",
        characters={
            "Narrator": CharacterProfile(voice_profile="deep, steady"),
            "Ghost": CharacterProfile(voice_profile="ethereal, whisper"),
        },
        segments=[
            ScriptSegment(type=SegmentType.NARRATION, character="Narrator", text="It was dark.", tone="ominous"),
            ScriptSegment(type=SegmentType.DIALOGUE, character="Ghost", text="I see you.", tone="menacing"),
            ScriptSegment(type=SegmentType.SFX, description="door creaking"),
        ],
    )
    pydantic_to_script(test_story, script)
    return test_story


@pytest.fixture
def story_with_audio(test_story):
    """Create a story with a script and an audio file path set."""
    script = NarrationScript(
        title="Audio Script",
        characters={
            "Narrator": CharacterProfile(voice_profile="deep, steady"),
            "Ghost": CharacterProfile(voice_profile="ethereal, whisper"),
        },
        segments=[
            ScriptSegment(type=SegmentType.NARRATION, character="Narrator", text="It was dark.", tone="ominous"),
            ScriptSegment(type=SegmentType.DIALOGUE, character="Ghost", text="I see you.", tone="menacing"),
        ],
    )
    pydantic_to_script(test_story, script)
    test_story.audio_file_path = "/data/stories/old_audio.mp3"
    test_story.save(update_fields=["audio_file_path"])
    return test_story


class TestScriptHelpers:
    def test_pydantic_to_script_and_back(self, test_story):
        original = NarrationScript(
            title="Round Trip",
            characters={
                "Narrator": CharacterProfile(voice_profile="calm, measured", voice_id="voice_1"),
                "Villain": CharacterProfile(voice_profile="raspy, menacing"),
            },
            segments=[
                ScriptSegment(type=SegmentType.NARRATION, character="Narrator", text="Hello.", tone="neutral"),
                ScriptSegment(type=SegmentType.DIALOGUE, character="Villain", text="Mwahaha", tone="evil"),
                ScriptSegment(type=SegmentType.PAUSE, duration_ms=1500),
                ScriptSegment(type=SegmentType.AMBIENT, description="wind howling", loop=True),
            ],
        )

        pydantic_to_script(test_story, original)
        restored = script_to_pydantic(test_story.script)

        assert restored.title == original.title
        assert len(restored.characters) == len(original.characters)
        assert len(restored.segments) == len(original.segments)
        assert restored.characters["Narrator"].voice_id == "voice_1"
        assert restored.segments[2].duration_ms == 1500
        assert restored.segments[3].loop is True


class TestGenerateScript:
    @patch("apps.tasks.executor.submit_task")
    def test_generate_script_creates_task(self, mock_submit, client, auth_headers, test_story):
        resp = client.post(
            "/api/audio/generate-script",
            data=json.dumps({"story_id": test_story.id}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data
        assert data["message"] == "Script generation started"

        # Verify task was created
        task = BackgroundTask.objects.get(id=data["task_id"])
        assert task.task_type == TaskType.GENERATE_SCRIPT
        assert task.story_id == test_story.id
        assert task.status == "queued"

        mock_submit.assert_called_once()

    def test_generate_script_story_not_found(self, client, auth_headers):
        resp = client.post(
            "/api/audio/generate-script",
            data=json.dumps({"story_id": 9999}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 404

    def test_generate_script_returns_existing(self, client, auth_headers, story_with_script):
        resp = client.post(
            "/api/audio/generate-script",
            data=json.dumps({"story_id": story_with_script.id}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Script already exists"

    def test_generate_script_unauthenticated(self, client, test_story):
        resp = client.post(
            "/api/audio/generate-script",
            data=json.dumps({"story_id": test_story.id}),
            content_type="application/json",
        )
        assert resp.status_code == 401

    @patch("apps.tasks.executor.submit_task")
    def test_generate_script_force_regenerate(self, mock_submit, client, auth_headers, story_with_script):
        """Story with existing script + force_regenerate=True still creates a task."""
        resp = client.post(
            "/api/audio/generate-script",
            data=json.dumps({"story_id": story_with_script.id, "force_regenerate": True}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data
        assert data["message"] == "Script generation started"

        task = BackgroundTask.objects.get(id=data["task_id"])
        assert task.task_type == TaskType.GENERATE_SCRIPT
        assert task.story_id == story_with_script.id

        mock_submit.assert_called_once()


class TestGetScript:
    def test_get_script_exists(self, client, story_with_script):
        resp = client.get(f"/api/audio/script/{story_with_script.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "script" in data
        assert data["segment_count"] == 3
        assert data["voice_segments"] == 2
        assert data["sfx_segments"] == 1

    def test_get_script_not_found(self, client, test_story):
        resp = client.get(f"/api/audio/script/{test_story.id}")
        assert resp.status_code == 404

    def test_get_script_story_not_found(self, client, db):
        resp = client.get("/api/audio/script/9999")
        assert resp.status_code == 404


class TestUpdateScript:
    def test_update_script(self, client, auth_headers, story_with_script):
        new_script = {
            "title": "Updated Script",
            "characters": {"Narrator": {"voice_profile": "updated voice"}},
            "segments": [
                {"type": "narration", "character": "Narrator", "text": "Updated text."},
            ],
        }
        resp = client.put(
            f"/api/audio/script/{story_with_script.id}",
            data=json.dumps(new_script),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Script updated"

    def test_update_script_invalid_character_ref(self, client, auth_headers, story_with_script):
        bad_script = {
            "title": "Bad Script",
            "characters": {"Narrator": {"voice_profile": "voice"}},
            "segments": [
                {"type": "dialogue", "character": "NonExistent", "text": "Hello"},
            ],
        }
        resp = client.put(
            f"/api/audio/script/{story_with_script.id}",
            data=json.dumps(bad_script),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 400

    def test_update_script_requires_auth(self, client, story_with_script):
        """PUT without auth headers returns 401."""
        new_script = {
            "title": "Updated Script",
            "characters": {"Narrator": {"voice_profile": "updated voice"}},
            "segments": [
                {"type": "narration", "character": "Narrator", "text": "Updated text."},
            ],
        }
        resp = client.put(
            f"/api/audio/script/{story_with_script.id}",
            data=json.dumps(new_script),
            content_type="application/json",
        )
        assert resp.status_code == 401

    @patch("apps.audio.api._delete_audio_file")
    def test_update_script_invalidates_audio(self, mock_delete, client, auth_headers, story_with_audio):
        """Editing a script on a story with existing audio clears audio_file_path and deletes the file."""
        old_path = story_with_audio.audio_file_path
        assert old_path  # precondition: audio exists

        new_script = {
            "title": "Edited Script",
            "characters": {"Narrator": {"voice_profile": "new voice"}},
            "segments": [
                {"type": "narration", "character": "Narrator", "text": "New text."},
            ],
        }
        resp = client.put(
            f"/api/audio/script/{story_with_audio.id}",
            data=json.dumps(new_script),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Script updated"

        # Verify audio_file_path was cleared
        story_with_audio.refresh_from_db()
        assert story_with_audio.audio_file_path == ""

        # Verify the old file deletion was attempted
        mock_delete.assert_called_once_with(old_path)

    def test_update_script_without_audio_succeeds(self, client, auth_headers, story_with_script):
        """Editing a script on a story without audio works fine (no audio to invalidate)."""
        assert not story_with_script.audio_file_path  # precondition: no audio

        new_script = {
            "title": "Edited Script",
            "characters": {"Narrator": {"voice_profile": "edited voice"}},
            "segments": [
                {"type": "narration", "character": "Narrator", "text": "Edited narration."},
            ],
        }
        resp = client.put(
            f"/api/audio/script/{story_with_script.id}",
            data=json.dumps(new_script),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Script updated"

        # Verify the script was actually updated
        story_with_script.refresh_from_db()
        restored = script_to_pydantic(story_with_script.script)
        assert restored.title == "Edited Script"

    def test_update_script_allows_defined_characters(self, client, auth_headers, story_with_script):
        """Segments that reference only defined characters should succeed."""
        valid_script = {
            "title": "Valid Multi-Character Script",
            "characters": {
                "Narrator": {"voice_profile": "calm"},
                "Detective": {"voice_profile": "gruff"},
            },
            "segments": [
                {"type": "narration", "character": "Narrator", "text": "The night was cold."},
                {"type": "dialogue", "character": "Detective", "text": "Who goes there?"},
                {"type": "narration", "character": "Narrator", "text": "He stepped forward."},
                {"type": "sfx", "description": "footsteps on gravel"},
            ],
        }
        resp = client.put(
            f"/api/audio/script/{story_with_script.id}",
            data=json.dumps(valid_script),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Script updated"
        assert sorted(resp.json()["characters"]) == ["Detective", "Narrator"]


class TestGenerateAudio:
    @patch("apps.audio.api.generate_audio")
    def test_generate_audio_success(self, mock_gen, client, auth_headers, test_story):
        mock_gen.return_value = "/data/stories/test.mp3"
        resp = client.post(
            "/api/audio/generate-audio",
            data=json.dumps({"story_id": test_story.id, "voice_id": "voice_123"}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["audio_file"] == "/data/stories/test.mp3"

    def test_generate_audio_story_not_found(self, client, auth_headers):
        resp = client.post(
            "/api/audio/generate-audio",
            data=json.dumps({"story_id": 9999, "voice_id": "voice_123"}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 404


class TestGenerateNarration:
    @patch("apps.tasks.executor.submit_task")
    @patch("apps.audio.api.auto_assign_voices")
    def test_generate_narration_creates_task(self, mock_assign, mock_submit, client, auth_headers, story_with_script):
        mock_assign.return_value = {"Narrator": "v1", "Ghost": "v2"}

        resp = client.post(
            "/api/audio/generate-narration",
            data=json.dumps({"story_id": story_with_script.id}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data
        assert data["message"] == "Narration generation started"

        # Verify task was created
        task = BackgroundTask.objects.get(id=data["task_id"])
        assert task.task_type == TaskType.GENERATE_NARRATION
        assert task.story_id == story_with_script.id
        assert task.status == "queued"

        mock_submit.assert_called_once()

    def test_generate_narration_no_script(self, client, auth_headers, test_story):
        resp = client.post(
            "/api/audio/generate-narration",
            data=json.dumps({"story_id": test_story.id}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 400

    @patch("apps.tasks.executor.submit_task")
    def test_explicit_voice_map(self, mock_submit, client, auth_headers, story_with_script):
        """Providing a complete voice_map skips auto_assign_voices and creates the task."""
        voice_map = {"Narrator": "voice_abc", "Ghost": "voice_def"}

        resp = client.post(
            "/api/audio/generate-narration",
            data=json.dumps({"story_id": story_with_script.id, "voice_map": voice_map}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data
        assert data["message"] == "Narration generation started"

        mock_submit.assert_called_once()

    def test_missing_character_in_voice_map(self, client, auth_headers, story_with_script):
        """Partial voice_map (missing characters) returns 400."""
        # story_with_script has Narrator + Ghost; only provide one
        partial_map = {"Narrator": "voice_abc"}

        resp = client.post(
            "/api/audio/generate-narration",
            data=json.dumps({"story_id": story_with_script.id, "voice_map": partial_map}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 400
        assert "Missing voice assignments" in resp.json()["detail"]

    def test_generate_narration_requires_auth(self, client, story_with_script):
        """POST without auth headers returns 401."""
        resp = client.post(
            "/api/audio/generate-narration",
            data=json.dumps({"story_id": story_with_script.id}),
            content_type="application/json",
        )
        assert resp.status_code == 401

    def test_generate_narration_story_not_found(self, client, auth_headers):
        """Nonexistent story_id returns 404."""
        resp = client.post(
            "/api/audio/generate-narration",
            data=json.dumps({"story_id": 9999}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 404

    @patch("apps.tasks.executor.submit_task")
    @patch("apps.audio.api.auto_assign_voices")
    def test_narration_persists_voice_ids(self, mock_assign, mock_submit, client, auth_headers, story_with_script):
        """After narration with auto-assigned voices, voice_ids are saved in the script's character models."""
        mock_assign.return_value = {"Narrator": "auto_v1", "Ghost": "auto_v2"}

        resp = client.post(
            "/api/audio/generate-narration",
            data=json.dumps({"story_id": story_with_script.id}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200

        # Reload and check that voice IDs were persisted into the Character models
        story_with_script.refresh_from_db()
        db_script = story_with_script.script
        characters = {c.name: c for c in db_script.characters.all()}

        assert characters["Narrator"].voice_id == "auto_v1"
        assert characters["Ghost"].voice_id == "auto_v2"
