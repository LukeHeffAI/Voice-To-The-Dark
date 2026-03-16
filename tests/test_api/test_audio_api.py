"""Tests for audio API endpoints."""

import json
from unittest.mock import MagicMock, patch

import pytest

from apps.audio.helpers import pydantic_to_script, script_to_pydantic
from apps.audio.models import NarrationScript as NarrationScriptModel
from apps.stories.models import Story
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
    @patch("apps.audio.api.generate_script")
    def test_generate_script_success(self, mock_gen, client, auth_headers, test_story):
        mock_script = NarrationScript(
            title="Generated",
            characters={"Narrator": CharacterProfile(voice_profile="deep")},
            segments=[ScriptSegment(type=SegmentType.NARRATION, character="Narrator", text="Text.")],
        )
        mock_gen.return_value = mock_script

        resp = client.post(
            "/api/audio/generate-script",
            data=json.dumps({"story_id": test_story.id}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Script generated successfully!"
        assert "Narrator" in data["characters"]
        mock_gen.assert_called_once()

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
    @patch("apps.audio.api.generate_narration")
    @patch("apps.audio.api.auto_assign_voices")
    def test_generate_narration_success(self, mock_assign, mock_gen, client, auth_headers, story_with_script):
        mock_assign.return_value = {"Narrator": "v1", "Ghost": "v2"}
        mock_result = MagicMock()
        mock_result.output_path = "/data/stories/narrated.mp3"
        mock_result.total_segments = 3
        mock_result.cache_hits = 1
        mock_result.cache_misses = 2
        mock_gen.return_value = mock_result

        resp = client.post(
            "/api/audio/generate-narration",
            data=json.dumps({"story_id": story_with_script.id}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["audio_file"] == "/data/stories/narrated.mp3"
        assert data["cache_stats"]["total_segments"] == 3

    def test_generate_narration_no_script(self, client, auth_headers, test_story):
        resp = client.post(
            "/api/audio/generate-narration",
            data=json.dumps({"story_id": test_story.id}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 400
