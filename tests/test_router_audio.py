"""Tests for the /audio router endpoints."""

import json
import pytest
from unittest.mock import patch, MagicMock
from app.models.story import Story
from app.schemas.narration import NarrationScript, ScriptSegment, CharacterProfile, SegmentType


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


class TestGenerateNarration:
    @patch("app.routers.audio.generate_narration")
    @patch("app.routers.audio.auto_assign_voices")
    def test_auto_assigns_voices(self, mock_voices, mock_gen, client, auth_headers, story_with_script, db_session):
        mock_voices.return_value = {"narrator": "voice_1", "sarah": "voice_2"}
        mock_gen.return_value = "/tmp/audio/output.mp3"

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
        mock_gen.return_value = "/tmp/audio/output.mp3"

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
