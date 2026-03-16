"""Tests for the audio API endpoints (/api/audio/)."""

import pytest
from unittest.mock import patch, MagicMock

from apps.accounts.auth import create_access_token
from apps.accounts.models import User
from apps.audio.models import GenerationTask
from apps.core.rate_limit import _request_log
from apps.stories.models import Story

from tests.conftest import post_json, put_json


# ── Helpers ──────────────────────────────────────────────────────────

SAMPLE_SCRIPT = {
    "title": "Test",
    "characters": {"Narrator": {"voice_profile": "deep, steady"}},
    "segments": [{"type": "narration", "character": "Narrator", "text": "Hello world"}],
}


def _make_story(db, **overrides):
    """Create a Story with sensible defaults, overridden by kwargs."""
    defaults = dict(
        title="Test Story",
        reddit_url="https://www.reddit.com/r/nosleep/comments/abc123/test_story/",
        text_content="Some spooky text content.",
        narration_text="Some spooky narration text.",
        content_hash="testhash000",
        part_count=1,
    )
    defaults.update(overrides)
    return Story.objects.create(**defaults)


# ── 1. TestGenerateAudio ─────────────────────────────────────────────


@pytest.mark.django_db
class TestGenerateAudio:
    @patch("apps.audio.api.elevenlabs_generate_audio", return_value="/tmp/test.mp3")
    def test_generate_audio_success(self, mock_tts, api_client, auth_headers, sample_story):
        resp = post_json(
            api_client,
            "/api/audio/generate-audio",
            {"story_id": sample_story.id, "voice_id": "voice123"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["audio_file"] == "/tmp/test.mp3"
        assert data["message"] == "Audio generated successfully!"
        mock_tts.assert_called_once()
        sample_story.refresh_from_db()
        assert sample_story.audio_file_path == "/tmp/test.mp3"

    def test_generate_audio_story_not_found(self, api_client, auth_headers, db):
        resp = post_json(
            api_client,
            "/api/audio/generate-audio",
            {"story_id": 9999, "voice_id": "voice123"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_generate_audio_already_generated(self, api_client, auth_headers, db):
        story = _make_story(db, audio_file_path="/tmp/existing.mp3")
        resp = post_json(
            api_client,
            "/api/audio/generate-audio",
            {"story_id": story.id, "voice_id": "voice123", "force_regenerate": False},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["audio_file"] == "/tmp/existing.mp3"
        assert data["message"] == "Already generated"

    @patch("apps.audio.api.elevenlabs_generate_audio", return_value="/tmp/new.mp3")
    def test_generate_audio_force_regenerate(self, mock_tts, api_client, auth_headers, db):
        story = _make_story(db, audio_file_path="/tmp/existing.mp3")
        resp = post_json(
            api_client,
            "/api/audio/generate-audio",
            {"story_id": story.id, "voice_id": "voice123", "force_regenerate": True},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["audio_file"] == "/tmp/new.mp3"
        mock_tts.assert_called_once()
        story.refresh_from_db()
        assert story.audio_file_path == "/tmp/new.mp3"

    def test_generate_audio_requires_auth(self, api_client, sample_story):
        resp = post_json(
            api_client,
            "/api/audio/generate-audio",
            {"story_id": sample_story.id, "voice_id": "voice123"},
        )
        assert resp.status_code == 401


# ── 2. TestGenerateScript ────────────────────────────────────────────


@pytest.mark.django_db
class TestGenerateScript:
    @patch("apps.audio.api.start_script_generation")
    def test_generates_task(self, mock_start, api_client, auth_headers, sample_story):
        resp = post_json(
            api_client,
            "/api/audio/generate-script",
            {"story_id": sample_story.id},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data
        task = GenerationTask.objects.get(id=data["task_id"])
        assert task.task_type == "script"
        assert task.status == "queued"
        assert task.story_id == sample_story.id
        mock_start.assert_called_once_with(task)

    def test_script_already_exists(self, api_client, auth_headers, db):
        story = _make_story(db, script_json=SAMPLE_SCRIPT)
        resp = post_json(
            api_client,
            "/api/audio/generate-script",
            {"story_id": story.id},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data
        task = GenerationTask.objects.get(id=data["task_id"])
        assert task.status == "completed"
        assert task.progress == 100
        assert task.result_json["message"] == "Script already exists"

    def test_story_not_found(self, api_client, auth_headers, db):
        resp = post_json(
            api_client,
            "/api/audio/generate-script",
            {"story_id": 9999},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    @patch("apps.audio.api.start_script_generation")
    def test_already_running_returns_existing_task(self, mock_start, api_client, auth_headers, sample_story, test_user):
        existing_task = GenerationTask.objects.create(
            user=test_user,
            story=sample_story,
            task_type="script",
            status="queued",
            stage="Queued",
        )
        resp = post_json(
            api_client,
            "/api/audio/generate-script",
            {"story_id": sample_story.id},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == existing_task.id
        mock_start.assert_not_called()

    def test_requires_auth(self, api_client, sample_story):
        resp = post_json(
            api_client,
            "/api/audio/generate-script",
            {"story_id": sample_story.id},
        )
        assert resp.status_code == 401

    @patch("apps.audio.api.start_script_generation")
    def test_no_text(self, mock_start, api_client, auth_headers, db):
        story = _make_story(db, text_content="", narration_text=None)
        resp = post_json(
            api_client,
            "/api/audio/generate-script",
            {"story_id": story.id},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        mock_start.assert_not_called()

    def test_rate_limited(self, api_client, auth_headers, sample_story):
        _request_log.clear()
        for i in range(10):
            resp = post_json(
                api_client,
                "/api/audio/generate-script",
                {"story_id": sample_story.id},
                headers=auth_headers,
            )
            assert resp.status_code == 200, f"Request {i+1} failed unexpectedly"

        resp = post_json(
            api_client,
            "/api/audio/generate-script",
            {"story_id": sample_story.id},
            headers=auth_headers,
        )
        assert resp.status_code == 429

    @patch("apps.audio.api.start_script_generation")
    def test_force_regenerate_ignores_existing_script(self, mock_start, api_client, auth_headers, db):
        story = _make_story(db, script_json=SAMPLE_SCRIPT)
        resp = post_json(
            api_client,
            "/api/audio/generate-script",
            {"story_id": story.id, "force_regenerate": True},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        task = GenerationTask.objects.get(id=data["task_id"])
        assert task.status == "queued"
        mock_start.assert_called_once()


# ── 3. TestGetScript ─────────────────────────────────────────────────


@pytest.mark.django_db
class TestGetScript:
    def test_returns_script(self, api_client, db):
        story = _make_story(db, script_json=SAMPLE_SCRIPT)
        resp = api_client.get(f"/api/audio/script/{story.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["script"]["title"] == "Test"
        assert "Narrator" in data["characters"]
        assert data["segment_count"] == 1

    def test_no_script(self, api_client, sample_story):
        resp = api_client.get(f"/api/audio/script/{sample_story.id}")
        assert resp.status_code == 404

    def test_story_not_found(self, api_client, db):
        resp = api_client.get("/api/audio/script/9999")
        assert resp.status_code == 404


# ── 4. TestUpdateScript ──────────────────────────────────────────────


@pytest.mark.django_db
class TestUpdateScript:
    def test_update_script(self, api_client, auth_headers, db):
        story = _make_story(db, script_json=SAMPLE_SCRIPT, audio_file_path="/tmp/old.mp3")
        new_script = {
            "title": "Updated",
            "characters": {"Narrator": {"voice_profile": "calm, warm"}},
            "segments": [{"type": "narration", "character": "Narrator", "text": "Updated text"}],
        }
        resp = put_json(
            api_client,
            f"/api/audio/script/{story.id}",
            new_script,
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Script updated"
        assert "Narrator" in data["characters"]
        story.refresh_from_db()
        assert story.script_json["title"] == "Updated"
        assert story.audio_file_path is None

    def test_story_not_found(self, api_client, auth_headers, db):
        resp = put_json(
            api_client,
            "/api/audio/script/9999",
            SAMPLE_SCRIPT,
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_requires_auth(self, api_client, sample_story):
        resp = put_json(
            api_client,
            f"/api/audio/script/{sample_story.id}",
            SAMPLE_SCRIPT,
        )
        assert resp.status_code == 401


# ── 5. TestGenerateNarration ─────────────────────────────────────────


@pytest.mark.django_db
class TestGenerateNarration:
    @patch("apps.audio.api.start_narration_generation")
    @patch("apps.audio.api.auto_assign_voices", return_value={"Narrator": "voice_abc"})
    def test_generates_task(self, mock_voices, mock_start, api_client, auth_headers, db):
        story = _make_story(db, script_json=SAMPLE_SCRIPT)
        resp = post_json(
            api_client,
            "/api/audio/generate-narration",
            {"story_id": story.id},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data
        task = GenerationTask.objects.get(id=data["task_id"])
        assert task.task_type == "narration"
        assert task.status == "queued"
        mock_voices.assert_called_once()
        mock_start.assert_called_once()

    def test_already_generated(self, api_client, auth_headers, db):
        story = _make_story(db, script_json=SAMPLE_SCRIPT, audio_file_path="/tmp/audio.mp3")
        resp = post_json(
            api_client,
            "/api/audio/generate-narration",
            {"story_id": story.id},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data
        task = GenerationTask.objects.get(id=data["task_id"])
        assert task.status == "completed"
        assert task.result_json["message"] == "Already generated"

    def test_no_script(self, api_client, auth_headers, sample_story):
        resp = post_json(
            api_client,
            "/api/audio/generate-narration",
            {"story_id": sample_story.id},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_story_not_found(self, api_client, auth_headers, db):
        resp = post_json(
            api_client,
            "/api/audio/generate-narration",
            {"story_id": 9999},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_requires_auth(self, api_client, sample_story):
        resp = post_json(
            api_client,
            "/api/audio/generate-narration",
            {"story_id": sample_story.id},
        )
        assert resp.status_code == 401

    @patch("apps.audio.api.start_narration_generation")
    @patch("apps.audio.api.auto_assign_voices", return_value={"Narrator": "voice_abc"})
    def test_already_running_returns_existing(self, mock_voices, mock_start, api_client, auth_headers, db, test_user):
        story = _make_story(db, script_json=SAMPLE_SCRIPT)
        existing_task = GenerationTask.objects.create(
            user=test_user,
            story=story,
            task_type="narration",
            status="queued",
            stage="Queued",
        )
        resp = post_json(
            api_client,
            "/api/audio/generate-narration",
            {"story_id": story.id},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == existing_task.id
        mock_start.assert_not_called()


# ── 6. TestTaskStatus ────────────────────────────────────────────────


@pytest.mark.django_db
class TestTaskStatus:
    def test_get_task_status(self, api_client, auth_headers, sample_story, test_user):
        task = GenerationTask.objects.create(
            user=test_user,
            story=sample_story,
            task_type="script",
            status="running",
            progress=50,
            stage="Adapting script",
        )
        resp = api_client.get(f"/api/audio/tasks/{task.id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == task.id
        assert data["task_type"] == "script"
        assert data["status"] == "running"
        assert data["progress"] == 50
        assert data["stage"] == "Adapting script"

    def test_task_not_found(self, api_client, auth_headers, db):
        resp = api_client.get("/api/audio/tasks/9999", headers=auth_headers)
        assert resp.status_code == 404

    def test_requires_auth(self, api_client, db):
        resp = api_client.get("/api/audio/tasks/1")
        assert resp.status_code == 401

    def test_other_user_task_not_found(self, api_client, auth_headers, sample_story, db):
        other_user = User.objects.create_user(username="otheruser", password="pass123")
        task = GenerationTask.objects.create(
            user=other_user,
            story=sample_story,
            task_type="script",
            status="running",
            progress=25,
            stage="Working",
        )
        resp = api_client.get(f"/api/audio/tasks/{task.id}", headers=auth_headers)
        assert resp.status_code == 404


# ── 7. TestActiveTask ────────────────────────────────────────────────


@pytest.mark.django_db
class TestActiveTask:
    def test_finds_active_task(self, api_client, auth_headers, sample_story, test_user):
        task = GenerationTask.objects.create(
            user=test_user,
            story=sample_story,
            task_type="script",
            status="queued",
            stage="Queued",
        )
        resp = api_client.get(
            f"/api/audio/tasks/active/{sample_story.id}", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == task.id
        assert data["status"] == "queued"

    def test_no_active_task(self, api_client, auth_headers, sample_story):
        resp = api_client.get(
            f"/api/audio/tasks/active/{sample_story.id}", headers=auth_headers
        )
        assert resp.status_code == 404

    def test_requires_auth(self, api_client, sample_story):
        resp = api_client.get(f"/api/audio/tasks/active/{sample_story.id}")
        assert resp.status_code == 401
