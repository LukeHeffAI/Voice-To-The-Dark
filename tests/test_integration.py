"""Integration tests for the full story-to-audio pipeline.

These tests mock external services (Reddit, Claude, ElevenLabs) but exercise
the full flow through multiple router calls and database state transitions.
"""

import json
import pytest
from unittest.mock import patch
from app.schemas.narration import NarrationScript, ScriptSegment, CharacterProfile, SegmentType


MOCK_SCRIPT = NarrationScript(
    title="The Haunted Basement",
    characters={
        "narrator": CharacterProfile(voice_profile="Deep, steady male narrator"),
        "emma": CharacterProfile(voice_profile="Young woman, frightened"),
    },
    segments=[
        ScriptSegment(type=SegmentType.NARRATION, character="narrator", text="It was a dark November evening."),
        ScriptSegment(type=SegmentType.DIALOGUE, character="emma", text="Did you hear that?"),
        ScriptSegment(type=SegmentType.SFX, description="floorboard creaking"),
        ScriptSegment(type=SegmentType.PAUSE, duration_ms=1500),
        ScriptSegment(type=SegmentType.NARRATION, character="narrator", text="The basement door swung open."),
    ],
)


class TestFullPipeline:
    """Test the submit → script → narration pipeline end to end."""

    @patch("app.routers.stories.fetch_post_metadata")
    @patch("app.routers.stories.fetch_multi_part_story")
    def test_submit_then_check_duplicate(self, mock_fetch, mock_metadata, client, auth_headers, db_session):
        """Submit a story, then verify duplicate check finds it."""
        mock_metadata.return_value = {"title": "The Haunted Basement", "author": "test_author"}
        mock_fetch.return_value = "It was a dark November evening. The old house creaked."

        url = "https://www.reddit.com/r/nosleep/comments/test123/the_haunted_basement/"

        # Submit
        resp = client.post("/stories/submit", json={"reddit_url": url}, headers=auth_headers)
        assert resp.status_code == 200
        story_id = resp.json()["id"]

        # Check duplicate
        resp = client.get("/stories/check-duplicate/", params={"reddit_url": url})
        assert resp.status_code == 200
        assert resp.json()["is_duplicate"] is True
        assert resp.json()["existing_story_id"] == story_id

    @patch("app.routers.stories.fetch_post_metadata")
    @patch("app.routers.stories.fetch_multi_part_story")
    @patch("app.routers.audio.generate_script")
    def test_submit_then_generate_script(self, mock_script, mock_fetch, mock_metadata, client, auth_headers, db_session):
        """Submit a story, then generate its script."""
        mock_metadata.return_value = {"title": "The Haunted Basement", "author": "test_author"}
        mock_fetch.return_value = "It was a dark November evening."
        mock_script.return_value = MOCK_SCRIPT

        url = "https://www.reddit.com/r/nosleep/comments/int1/pipeline_test/"

        # Submit
        resp = client.post("/stories/submit", json={"reddit_url": url}, headers=auth_headers)
        story_id = resp.json()["id"]

        # Generate script
        resp = client.post("/audio/generate-script", json={"story_id": story_id}, headers=auth_headers)
        assert resp.status_code == 200
        assert "narrator" in resp.json()["characters"]
        assert "emma" in resp.json()["characters"]

        # Retrieve the script
        resp = client.get(f"/audio/script/{story_id}")
        assert resp.status_code == 200
        assert resp.json()["segment_count"] == 5

    @patch("app.routers.stories.fetch_post_metadata")
    @patch("app.routers.stories.fetch_multi_part_story")
    @patch("app.routers.audio.generate_script")
    @patch("app.routers.audio.generate_narration")
    @patch("app.routers.audio.auto_assign_voices")
    def test_full_pipeline_submit_script_narrate(
        self, mock_voices, mock_narrate, mock_script, mock_fetch, mock_metadata,
        client, auth_headers, db_session,
    ):
        """Submit → script → narration → verify audio path is stored."""
        mock_metadata.return_value = {"title": "Full Pipeline Test", "author": "test_author"}
        mock_fetch.return_value = "A terrifying encounter in the woods."
        mock_script.return_value = MOCK_SCRIPT
        mock_voices.return_value = {"narrator": "voice_1", "emma": "voice_2"}
        mock_narrate.return_value = "/tmp/audio/full_test.mp3"

        url = "https://www.reddit.com/r/nosleep/comments/full/pipeline/"

        # Step 1: Submit
        resp = client.post("/stories/submit", json={"reddit_url": url}, headers=auth_headers)
        assert resp.status_code == 200
        story_id = resp.json()["id"]

        # Step 2: Generate script
        resp = client.post("/audio/generate-script", json={"story_id": story_id}, headers=auth_headers)
        assert resp.status_code == 200

        # Step 3: Generate narration (auto-voices)
        resp = client.post("/audio/generate-narration", json={"story_id": story_id}, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["audio_file"] == "/tmp/audio/full_test.mp3"
        assert data["segments_processed"] == 5

        # Verify story now has audio path
        resp = client.get(f"/stories/{story_id}")
        assert resp.json()["audio_file_path"] == "/tmp/audio/full_test.mp3"

    @patch("app.routers.stories.fetch_post_metadata")
    @patch("app.routers.stories.fetch_multi_part_story")
    def test_resubmit_returns_existing(self, mock_fetch, mock_metadata, client, auth_headers, db_session):
        """Submitting the same URL twice returns the same story without re-fetching."""
        mock_metadata.return_value = {"title": "Duplicate Test", "author": "test_author"}
        mock_fetch.return_value = "Story content here."

        url = "https://www.reddit.com/r/nosleep/comments/dup/test/"

        # First submit
        resp1 = client.post("/stories/submit", json={"reddit_url": url}, headers=auth_headers)
        assert resp1.status_code == 200
        id1 = resp1.json()["id"]

        # Reset mock call count
        mock_metadata.reset_mock()
        mock_fetch.reset_mock()

        # Second submit - should return existing
        resp2 = client.post("/stories/submit", json={"reddit_url": url}, headers=auth_headers)
        assert resp2.status_code == 200
        assert resp2.json()["id"] == id1

        # Should NOT have fetched from Reddit again
        mock_metadata.assert_not_called()
        mock_fetch.assert_not_called()


class TestPlaybackFlow:
    """Test the playback state save/resume flow."""

    @patch("app.routers.stories.fetch_post_metadata")
    @patch("app.routers.stories.fetch_multi_part_story")
    def test_save_and_resume_position(self, mock_fetch, mock_metadata, client, auth_headers, db_session):
        mock_metadata.return_value = {"title": "Playback Test", "author": "test_author"}
        mock_fetch.return_value = "Story for playback testing."

        url = "https://www.reddit.com/r/nosleep/comments/play/test/"
        resp = client.post("/stories/submit", json={"reddit_url": url}, headers=auth_headers)
        story_id = resp.json()["id"]

        # Initially no playback position
        resp = client.get(f"/stories/playback/{story_id}")
        assert resp.json()["position_seconds"] == 0.0

        # Save position at 30 seconds
        client.post("/stories/playback", json={
            "story_id": story_id,
            "position_seconds": 30.0,
        })

        # Resume from saved position
        resp = client.get(f"/stories/playback/{story_id}")
        assert resp.json()["position_seconds"] == 30.0

        # Update position to 120 seconds
        client.post("/stories/playback", json={
            "story_id": story_id,
            "position_seconds": 120.0,
        })
        resp = client.get(f"/stories/playback/{story_id}")
        assert resp.json()["position_seconds"] == 120.0


class TestAuthFlow:
    """Test the auth lifecycle: login → access protected resource → logout."""

    def test_login_access_logout(self, client, test_user, db_session):
        # Login
        resp = client.post("/auth/login", json={
            "username": "testuser",
            "password": "testpass123",
        })
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Access protected endpoint
        resp = client.get("/auth/me", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["username"] == "testuser"

        # Logout (cookie-based, token still works until expiry)
        resp = client.post("/auth/logout")
        assert resp.status_code == 200
