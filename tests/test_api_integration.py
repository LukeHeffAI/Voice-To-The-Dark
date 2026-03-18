"""Integration tests for the Django API — full pipeline flows."""

import json

import pytest
from unittest.mock import MagicMock, patch

from apps.audio.models import GenerationTask
from apps.audio.schemas import CharacterProfile, NarrationScript, ScriptSegment, SegmentType
from apps.stories.models import Story
from tests.conftest import post_json, put_json

SAMPLE_SCRIPT = NarrationScript(
    title="Test Story",
    characters={"Narrator": CharacterProfile(voice_profile="deep, steady")},
    segments=[ScriptSegment(type=SegmentType.NARRATION, character="Narrator", text="It was dark.")],
)


@pytest.mark.django_db
class TestSubmitThenGenerate:
    """Full pipeline: submit story → generate script → generate narration."""

    @patch("apps.stories.api.find_series_parts", return_value=[])
    @patch("apps.stories.api.fetch_post_metadata")
    @patch("apps.stories.api.fetch_story_text")
    def test_submit_story(self, mock_text, mock_meta, mock_series, api_client, auth_headers):
        mock_meta.return_value = {"title": "Integration Test", "author": "tester"}
        mock_text.return_value = "The basement was silent except for the scratching."
        resp = post_json(api_client, "/api/stories/submit", {
            "reddit_url": "https://www.reddit.com/r/nosleep/comments/int123/integration_test/",
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Integration Test"
        assert data["id"] > 0

    @patch("apps.audio.api.start_script_generation")
    def test_submit_then_generate_script(self, mock_start, api_client, auth_headers):
        # First submit a story
        story = Story.objects.create(
            title="Pipeline Test",
            text_content="The hallway stretched on forever.",
            narration_text="The hallway stretched on forever.",
            content_hash="pipeline_hash_123",
        )
        resp = post_json(api_client, "/api/audio/generate-script", {
            "story_id": story.id,
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data
        task = GenerationTask.objects.get(id=data["task_id"])
        assert task.task_type == "script"
        assert task.status == "queued"
        mock_start.assert_called_once()

    @patch("apps.audio.api.start_narration_generation")
    @patch("apps.audio.api.auto_assign_voices")
    def test_full_pipeline_to_narration(self, mock_voices, mock_start, api_client, auth_headers):
        mock_voices.return_value = {"Narrator": "voice_123"}
        story = Story.objects.create(
            title="Full Pipeline",
            text_content="Content",
            narration_text="Content",
            content_hash="full_pipe_hash",
            script_json=SAMPLE_SCRIPT.model_dump(),
        )
        resp = post_json(api_client, "/api/audio/generate-narration", {
            "story_id": story.id,
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data
        task = GenerationTask.objects.get(id=data["task_id"])
        assert task.task_type == "narration"


@pytest.mark.django_db
class TestDuplicateDetection:
    def test_submit_duplicate_url_returns_existing(self, api_client, auth_headers, sample_story):
        resp = post_json(api_client, "/api/stories/submit", {
            "reddit_url": sample_story.reddit_url,
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == sample_story.id

    def test_check_duplicate_endpoint(self, api_client, sample_story):
        url = sample_story.reddit_url
        resp = api_client.get(f"/api/stories/check-duplicate/?reddit_url={url}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_duplicate"] is True
        assert data["existing_story_id"] == sample_story.id


@pytest.mark.django_db
class TestTaskLifecycle:
    """Test task state transitions via API + direct runner."""

    @patch("apps.audio.task_runner.generate_script")
    @patch("apps.audio.task_runner.close_old_connections")
    def test_script_task_lifecycle(self, mock_close, mock_gen, api_client, auth_headers):
        mock_gen.return_value = SAMPLE_SCRIPT

        story = Story.objects.create(
            title="Lifecycle Test",
            text_content="Something lurked beneath the stairs.",
            narration_text="Something lurked beneath the stairs.",
            content_hash="lifecycle_hash",
        )

        # Start script generation — mock start_script_generation to actually run sync
        with patch("apps.audio.api.start_script_generation") as mock_start:
            resp = post_json(api_client, "/api/audio/generate-script", {
                "story_id": story.id,
            }, headers=auth_headers)
            assert resp.status_code == 200
            task_id = resp.json()["task_id"]

        # Simulate the runner running synchronously
        from apps.audio.task_runner import _run_script_task
        _run_script_task(task_id)

        # Task should now be completed
        task = GenerationTask.objects.get(id=task_id)
        assert task.status == "completed"
        assert task.progress == 100

        # Poll task status via API
        resp = api_client.get(f"/api/audio/tasks/{task_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["progress"] == 100

        # Story should have script_json set
        story.refresh_from_db()
        assert story.script_json is not None

    @patch("apps.audio.task_runner.generate_script")
    @patch("apps.audio.task_runner.close_old_connections")
    def test_failed_task_lifecycle(self, mock_close, mock_gen, api_client, auth_headers):
        mock_gen.side_effect = RuntimeError("API call failed")

        story = Story.objects.create(
            title="Fail Test",
            text_content="The shadows moved.",
            narration_text="The shadows moved.",
            content_hash="fail_hash",
        )

        with patch("apps.audio.api.start_script_generation"):
            resp = post_json(api_client, "/api/audio/generate-script", {
                "story_id": story.id,
            }, headers=auth_headers)
            task_id = resp.json()["task_id"]

        from apps.audio.task_runner import _run_script_task
        _run_script_task(task_id)

        task = GenerationTask.objects.get(id=task_id)
        assert task.status == "failed"
        assert "API call failed" in task.error_message

        resp = api_client.get(f"/api/audio/tasks/{task_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "failed"
