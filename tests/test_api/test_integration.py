"""Integration tests for the full story-to-audio pipeline (Django).

These tests mock external services (Reddit, Claude, ElevenLabs) but exercise
the full flow through multiple API calls and database state transitions.
"""

import json
from unittest.mock import patch

import pytest

from apps.audio.helpers import pydantic_to_script
from apps.stories.models import Story
from apps.tasks.models import BackgroundTask, TaskType
from schemas.narration import CharacterProfile, NarrationScript, ScriptSegment, SegmentType


pytestmark = pytest.mark.django_db


MOCK_SCRIPT = NarrationScript(
    title="The Haunted Basement",
    characters={
        "Narrator": CharacterProfile(voice_profile="Deep, steady male narrator"),
        "Emma": CharacterProfile(voice_profile="Young woman, frightened"),
    },
    segments=[
        ScriptSegment(type=SegmentType.NARRATION, character="Narrator", text="It was a dark November evening."),
        ScriptSegment(type=SegmentType.DIALOGUE, character="Emma", text="Did you hear that?"),
        ScriptSegment(type=SegmentType.SFX, description="floorboard creaking"),
        ScriptSegment(type=SegmentType.PAUSE, duration_ms=1500),
        ScriptSegment(type=SegmentType.NARRATION, character="Narrator", text="The basement door swung open."),
    ],
)


class TestSubmitThenCheckDuplicate:
    """Test the submit → duplicate check flow."""

    @patch("apps.stories.api.find_series_parts", return_value=[])
    @patch("apps.stories.api.clean_for_narration", return_value="Cleaned text")
    @patch("apps.stories.api.hash_content", return_value="unique_integration_hash")
    @patch("apps.stories.api.fetch_story_text", return_value="It was a dark November evening.")
    @patch("apps.stories.api.fetch_post_metadata", return_value={"title": "The Haunted Basement", "author": "test_author"})
    def test_submit_then_check_duplicate(self, mock_meta, mock_text, mock_hash, mock_clean, mock_series, client, auth_headers):
        url = "https://www.reddit.com/r/nosleep/comments/test123/the_haunted_basement/"

        # Submit
        resp = client.post(
            "/api/stories/submit",
            data=json.dumps({"reddit_url": url}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200
        story_id = resp.json()["id"]

        # Check duplicate
        resp = client.get(f"/api/stories/check-duplicate/?reddit_url={url}")
        assert resp.status_code == 200
        assert resp.json()["is_duplicate"] is True
        assert resp.json()["existing_story_id"] == story_id


class TestSubmitThenScript:
    """Test the submit → generate script flow."""

    @patch("apps.tasks.executor.submit_task")
    @patch("apps.stories.api.find_series_parts", return_value=[])
    @patch("apps.stories.api.clean_for_narration", return_value="Cleaned text")
    @patch("apps.stories.api.hash_content", return_value="unique_script_hash")
    @patch("apps.stories.api.fetch_story_text", return_value="The basement door creaked open.")
    @patch("apps.stories.api.fetch_post_metadata", return_value={"title": "The Basement", "author": "ghost"})
    def test_submit_then_generate_script(self, mock_meta, mock_text, mock_hash, mock_clean, mock_series, mock_submit_task, client, auth_headers):
        url = "https://www.reddit.com/r/nosleep/comments/abc/the_basement/"

        # Submit story
        resp = client.post(
            "/api/stories/submit",
            data=json.dumps({"reddit_url": url}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200
        story_id = resp.json()["id"]

        # Generate script (creates background task)
        resp = client.post(
            "/api/audio/generate-script",
            data=json.dumps({"story_id": story_id}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data
        assert data["message"] == "Script generation started"

        # Verify background task was created
        task = BackgroundTask.objects.get(id=data["task_id"])
        assert task.task_type == TaskType.GENERATE_SCRIPT
        assert task.story_id == story_id
        mock_submit_task.assert_called_once()


class TestScriptEditThenNarration:
    """Test the edit script → generate narration flow."""

    @patch("apps.tasks.executor.submit_task")
    @patch("apps.audio.api.auto_assign_voices")
    def test_edit_script_then_narrate(self, mock_assign, mock_submit_task, client, auth_headers, test_story):
        # Create a script for the story
        pydantic_to_script(test_story, MOCK_SCRIPT)

        # Edit the script
        edited_script = MOCK_SCRIPT.model_dump()
        edited_script["title"] = "Edited Title"
        resp = client.put(
            f"/api/audio/script/{test_story.id}",
            data=json.dumps(edited_script),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Script updated"

        # Verify script was updated
        resp = client.get(f"/api/audio/script/{test_story.id}")
        assert resp.status_code == 200
        assert resp.json()["script"]["title"] == "Edited Title"

        # Generate narration (creates background task)
        mock_assign.return_value = {"Narrator": "voice_1", "Emma": "voice_2"}
        resp = client.post(
            "/api/audio/generate-narration",
            data=json.dumps({"story_id": test_story.id}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data
        assert data["message"] == "Narration generation started"

        task = BackgroundTask.objects.get(id=data["task_id"])
        assert task.task_type == TaskType.GENERATE_NARRATION
        mock_submit_task.assert_called_once()


class TestPlaybackPersistence:
    """Test that playback position persists across requests."""

    def test_save_and_retrieve_playback(self, client, auth_headers, test_user, test_story):
        # Save position
        resp = client.post(
            "/api/stories/playback",
            data=json.dumps({"story_id": test_story.id, "position_seconds": 42.5}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200

        # Retrieve position
        resp = client.get(f"/api/stories/playback/{test_story.id}", **auth_headers)
        assert resp.status_code == 200
        assert resp.json()["position_seconds"] == 42.5

        # Update position
        resp = client.post(
            "/api/stories/playback",
            data=json.dumps({"story_id": test_story.id, "position_seconds": 120.0}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200

        # Verify updated
        resp = client.get(f"/api/stories/playback/{test_story.id}", **auth_headers)
        assert resp.status_code == 200
        assert resp.json()["position_seconds"] == 120.0
