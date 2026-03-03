"""Tests for the /audio router endpoints."""

import json
import pytest
from unittest.mock import patch, MagicMock
from app.models.story import Story
from app.schemas.narration import NarrationScript, ScriptSegment, CharacterProfile, SegmentType
from app.services.narration_generator import NarrationResult


SAMPLE_SCRIPT = NarrationScript(
    title="Test Story",
    characters={
        "narrator": CharacterProfile(voice_profile="Deep male narrator"),
        "sarah": CharacterProfile(voice_profile="Young woman, scared"),
    },
    segments=[
        ScriptSegment(type=SegmentType.NARRATION, character="narrator", text="The night was dark."),
        ScriptSegment(type=SegmentType.DIALOGUE, character="sarah", text="Who's there?"),
        ScriptSegment(type=SegmentType.SFX, description="door creaking"),
    ],
)


def _narration_result(output_path="/tmp/audio/output.mp3", cache_hits=0, cache_misses=3, total_segments=3):
    """Helper to create a NarrationResult for test mocks."""
    return NarrationResult(
        output_path=output_path,
        cache_hits=cache_hits,
        cache_misses=cache_misses,
        total_segments=total_segments,
    )


@pytest.fixture()
def story_with_script(db_session):
    story = Story(
        title="Scripted Story",
        reddit_url="https://www.reddit.com/r/nosleep/comments/scripted/test/",
        text_content="The night was dark and full of terrors.",
        narration_text="The night was dark and full of terrors.",
        content_hash="script123",
        script_json=json.dumps(SAMPLE_SCRIPT.model_dump()),
        part_count=1,
    )
    db_session.add(story)
    db_session.commit()
    db_session.refresh(story)
    return story


@pytest.fixture()
def story_with_audio(db_session):
    """Story that has both a script and generated audio."""
    story = Story(
        title="Audio Story",
        reddit_url="https://www.reddit.com/r/nosleep/comments/audio/test/",
        text_content="Dark tale.",
        narration_text="Dark tale.",
        content_hash="audio456",
        script_json=json.dumps(SAMPLE_SCRIPT.model_dump()),
        audio_file_path="/tmp/audio/old_audio.mp3",
        part_count=1,
    )
    db_session.add(story)
    db_session.commit()
    db_session.refresh(story)
    return story


class TestGenerateScript:
    @patch("app.routers.audio.generate_script")
    def test_generates_script(self, mock_gen, client, auth_headers, sample_story, db_session):
        mock_gen.return_value = SAMPLE_SCRIPT
        resp = client.post("/audio/generate-script", json={
            "story_id": sample_story.id,
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Script generated successfully!"
        assert "narrator" in data["characters"]
        assert "sarah" in data["characters"]

    def test_returns_existing_script(self, client, auth_headers, story_with_script, db_session):
        resp = client.post("/audio/generate-script", json={
            "story_id": story_with_script.id,
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["message"] == "Script already exists"

    @patch("app.routers.audio.generate_script")
    def test_force_regenerate(self, mock_gen, client, auth_headers, story_with_script, db_session):
        mock_gen.return_value = SAMPLE_SCRIPT
        resp = client.post("/audio/generate-script", json={
            "story_id": story_with_script.id,
            "force_regenerate": True,
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["message"] == "Script generated successfully!"
        mock_gen.assert_called_once()

    def test_requires_auth(self, client, sample_story, db_session):
        resp = client.post("/audio/generate-script", json={
            "story_id": sample_story.id,
        })
        assert resp.status_code == 401

    def test_story_not_found(self, client, auth_headers, db_session):
        resp = client.post("/audio/generate-script", json={
            "story_id": 9999,
        }, headers=auth_headers)
        assert resp.status_code == 404


class TestGetScript:
    def test_returns_script(self, client, story_with_script, db_session):
        resp = client.get(f"/audio/script/{story_with_script.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["segment_count"] == 3
        assert data["voice_segments"] == 2
        assert data["sfx_segments"] == 1

    def test_no_script_yet(self, client, sample_story, db_session):
        resp = client.get(f"/audio/script/{sample_story.id}")
        assert resp.status_code == 404

    def test_story_not_found(self, client, db_session):
        resp = client.get("/audio/script/9999")
        assert resp.status_code == 404


class TestUpdateScript:
    def test_update_script(self, client, auth_headers, story_with_script, db_session):
        updated = SAMPLE_SCRIPT.model_dump()
        updated["title"] = "Updated Title"
        resp = client.put(
            f"/audio/script/{story_with_script.id}",
            json=updated,
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "narrator" in resp.json()["characters"]

    def test_requires_auth(self, client, story_with_script, db_session):
        resp = client.put(
            f"/audio/script/{story_with_script.id}",
            json=SAMPLE_SCRIPT.model_dump(),
        )
        assert resp.status_code == 401

    # --- Bug fix: audio invalidation on script edit ---

    @patch("app.routers.audio._delete_audio_file")
    def test_edit_clears_audio_file_path(self, mock_delete, client, auth_headers, story_with_audio, db_session):
        """Editing a script should clear audio_file_path and delete the old file."""
        assert story_with_audio.audio_file_path is not None

        resp = client.put(
            f"/audio/script/{story_with_audio.id}",
            json=SAMPLE_SCRIPT.model_dump(),
            headers=auth_headers,
        )
        assert resp.status_code == 200

        # Audio should be invalidated
        db_session.refresh(story_with_audio)
        assert story_with_audio.audio_file_path is None

        # Old file should have been deleted
        mock_delete.assert_called_once_with("/tmp/audio/old_audio.mp3")

    def test_edit_without_audio_succeeds(self, client, auth_headers, story_with_script, db_session):
        """Editing a script that has no audio should work without errors."""
        assert story_with_script.audio_file_path is None
        resp = client.put(
            f"/audio/script/{story_with_script.id}",
            json=SAMPLE_SCRIPT.model_dump(),
            headers=auth_headers,
        )
        assert resp.status_code == 200

    # --- Character validation ---

    def test_rejects_unknown_character_in_segments(self, client, auth_headers, story_with_script, db_session):
        """Segments referencing characters not in the characters dict should be rejected."""
        script_data = SAMPLE_SCRIPT.model_dump()
        # Add a segment with an undefined character
        script_data["segments"].append({
            "type": "dialogue",
            "character": "ghost",
            "text": "I am not defined.",
        })
        resp = client.put(
            f"/audio/script/{story_with_script.id}",
            json=script_data,
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "ghost" in resp.json()["detail"]

    def test_allows_segments_with_defined_characters(self, client, auth_headers, story_with_script, db_session):
        """Segments referencing defined characters should pass validation."""
        resp = client.put(
            f"/audio/script/{story_with_script.id}",
            json=SAMPLE_SCRIPT.model_dump(),
            headers=auth_headers,
        )
        assert resp.status_code == 200


class TestGenerateNarration:
    @patch("app.routers.audio.generate_narration")
    @patch("app.routers.audio.auto_assign_voices")
    def test_auto_assigns_voices(self, mock_voices, mock_gen, client, auth_headers, story_with_script, db_session):
        mock_voices.return_value = {"narrator": "voice_1", "sarah": "voice_2"}
        mock_gen.return_value = _narration_result()

        resp = client.post("/audio/generate-narration", json={
            "story_id": story_with_script.id,
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Narration generated successfully!"
        assert data["voice_assignments"]["narrator"] == "voice_1"
        mock_voices.assert_called_once()

    @patch("app.routers.audio.generate_narration")
    def test_explicit_voice_map(self, mock_gen, client, auth_headers, story_with_script, db_session):
        mock_gen.return_value = _narration_result()

        resp = client.post("/audio/generate-narration", json={
            "story_id": story_with_script.id,
            "voice_map": {"narrator": "voice_a", "sarah": "voice_b"},
        }, headers=auth_headers)
        assert resp.status_code == 200

    @patch("app.routers.audio.generate_narration")
    def test_missing_character_in_voice_map(self, mock_gen, client, auth_headers, story_with_script, db_session):
        resp = client.post("/audio/generate-narration", json={
            "story_id": story_with_script.id,
            "voice_map": {"narrator": "voice_a"},  # Missing "sarah"
        }, headers=auth_headers)
        assert resp.status_code == 400
        assert "Missing voice assignments" in resp.json()["detail"]

    def test_no_script_returns_400(self, client, auth_headers, sample_story, db_session):
        resp = client.post("/audio/generate-narration", json={
            "story_id": sample_story.id,
        }, headers=auth_headers)
        assert resp.status_code == 400
        assert "No script found" in resp.json()["detail"]

    def test_requires_auth(self, client, story_with_script, db_session):
        resp = client.post("/audio/generate-narration", json={
            "story_id": story_with_script.id,
        })
        assert resp.status_code == 401

    def test_story_not_found(self, client, auth_headers, db_session):
        resp = client.post("/audio/generate-narration", json={
            "story_id": 9999,
        }, headers=auth_headers)
        assert resp.status_code == 404

    # --- Cache stats in response ---

    @patch("app.routers.audio.generate_narration")
    @patch("app.routers.audio.auto_assign_voices")
    def test_response_includes_cache_stats(self, mock_voices, mock_gen, client, auth_headers, story_with_script, db_session):
        mock_voices.return_value = {"narrator": "voice_1", "sarah": "voice_2"}
        mock_gen.return_value = _narration_result(cache_hits=2, cache_misses=1, total_segments=3)

        resp = client.post("/audio/generate-narration", json={
            "story_id": story_with_script.id,
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["cache_stats"]["total_segments"] == 3
        assert data["cache_stats"]["cache_hits"] == 2
        assert data["cache_stats"]["cache_misses"] == 1
        assert data["cache_stats"]["api_calls_saved"] == 2

    # --- Voice ID persistence into character profiles ---

    @patch("app.routers.audio.generate_narration")
    @patch("app.routers.audio.auto_assign_voices")
    def test_persists_voice_ids_into_script(self, mock_voices, mock_gen, client, auth_headers, story_with_script, db_session):
        """After narration generation, voice IDs should be written into CharacterProfile.voice_id."""
        mock_voices.return_value = {"narrator": "voice_1", "sarah": "voice_2"}
        mock_gen.return_value = _narration_result()

        resp = client.post("/audio/generate-narration", json={
            "story_id": story_with_script.id,
        }, headers=auth_headers)
        assert resp.status_code == 200

        # Check the script_json was updated with voice_ids
        db_session.refresh(story_with_script)
        script = NarrationScript(**json.loads(story_with_script.script_json))
        assert script.characters["narrator"].voice_id == "voice_1"
        assert script.characters["sarah"].voice_id == "voice_2"

    # --- Old audio file cleanup on regeneration ---

    @patch("app.routers.audio._delete_audio_file")
    @patch("app.routers.audio.generate_narration")
    @patch("app.routers.audio.auto_assign_voices")
    def test_deletes_old_audio_on_regeneration(self, mock_voices, mock_gen, mock_delete, client, auth_headers, story_with_audio, db_session):
        """Force-regenerating should delete the old audio file."""
        mock_voices.return_value = {"narrator": "voice_1", "sarah": "voice_2"}
        mock_gen.return_value = _narration_result(output_path="/tmp/audio/new.mp3")

        resp = client.post("/audio/generate-narration", json={
            "story_id": story_with_audio.id,
            "force_regenerate": True,
        }, headers=auth_headers)
        assert resp.status_code == 200
        mock_delete.assert_called_once_with("/tmp/audio/old_audio.mp3")

    # --- bust_cache parameter ---

    @patch("app.routers.audio.generate_narration")
    @patch("app.routers.audio.auto_assign_voices")
    def test_bust_cache_passed_to_generator(self, mock_voices, mock_gen, client, auth_headers, story_with_script, db_session):
        """The bust_cache flag should be passed through to generate_narration."""
        mock_voices.return_value = {"narrator": "voice_1", "sarah": "voice_2"}
        mock_gen.return_value = _narration_result()

        resp = client.post("/audio/generate-narration", json={
            "story_id": story_with_script.id,
            "bust_cache": True,
        }, headers=auth_headers)
        assert resp.status_code == 200
        mock_gen.assert_called_once()
        assert mock_gen.call_args.kwargs["bust_cache"] is True
