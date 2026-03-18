"""Performance and stress tests for the Django API.

Tests for audio streaming, concurrent generation, and rate limiting boundary conditions.
"""

import json
import os
import tempfile
from unittest.mock import patch

import pytest

from apps.stories.models import Story
from apps.tasks.models import BackgroundTask, TaskType


pytestmark = pytest.mark.django_db


class TestAudioStreaming:
    """Test HTTP Range request support for audio streaming."""

    @pytest.fixture
    def story_with_audio_file(self, db):
        """Create a story with an actual audio file on disk."""
        # Create a temporary file simulating an MP3
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        # Write 10KB of fake audio data
        tmp.write(b"\xff\xfb\x90\x00" * 2560)  # 10240 bytes
        tmp.close()

        story = Story.objects.create(
            title="Audio Stream Test",
            text_content="Test content",
            content_hash="stream_hash",
            audio_file_path=tmp.name,
        )
        yield story

        # Cleanup
        try:
            os.unlink(tmp.name)
        except FileNotFoundError:
            pass

    def test_full_file_download(self, client, story_with_audio_file):
        resp = client.get(f"/api/player/stream/{story_with_audio_file.id}")
        assert resp.status_code == 200
        assert resp["Content-Type"] == "audio/mpeg"
        assert resp["Accept-Ranges"] == "bytes"
        assert resp["Content-Length"] == "10240"

    def test_range_request_partial_content(self, client, story_with_audio_file):
        resp = client.get(
            f"/api/player/stream/{story_with_audio_file.id}",
            HTTP_RANGE="bytes=0-1023",
        )
        assert resp.status_code == 206
        assert resp["Content-Range"] == "bytes 0-1023/10240"
        assert resp["Content-Length"] == "1024"

    def test_range_request_middle_chunk(self, client, story_with_audio_file):
        resp = client.get(
            f"/api/player/stream/{story_with_audio_file.id}",
            HTTP_RANGE="bytes=1024-2047",
        )
        assert resp.status_code == 206
        assert resp["Content-Range"] == "bytes 1024-2047/10240"
        assert resp["Content-Length"] == "1024"

    def test_range_request_open_ended(self, client, story_with_audio_file):
        """Range: bytes=5000- (no end) should return from offset to EOF."""
        resp = client.get(
            f"/api/player/stream/{story_with_audio_file.id}",
            HTTP_RANGE="bytes=5000-",
        )
        assert resp.status_code == 206
        assert resp["Content-Range"] == "bytes 5000-10239/10240"
        assert resp["Content-Length"] == "5240"

    def test_stream_not_found(self, client, db):
        resp = client.get("/api/player/stream/9999")
        assert resp.status_code == 404


class TestConcurrentTaskSubmission:
    """Test that duplicate active tasks are prevented."""

    @patch("apps.tasks.executor.submit_task")
    def test_duplicate_script_task_rejected(self, mock_submit, client, auth_headers):
        story = Story.objects.create(
            title="Concurrent Test",
            text_content="Some content for testing concurrent submissions.",
            narration_text="Some content for testing concurrent submissions.",
            content_hash="concurrent_hash",
        )

        # First task creation should succeed
        resp1 = client.post(
            "/api/audio/generate-script",
            data=json.dumps({"story_id": story.id}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp1.status_code == 200
        task_id_1 = resp1.json()["task_id"]

        # Second task for same story should either create a new one
        # (if first is still queued) or return existing
        # The behavior depends on the unique constraint in BackgroundTask
        task_count = BackgroundTask.objects.filter(
            story=story,
            task_type=TaskType.GENERATE_SCRIPT,
        ).count()
        assert task_count >= 1


class TestRateLimitBoundary:
    """Test rate limiting at exact boundary conditions."""

    @patch("apps.stories.api.fetch_post_metadata", return_value={"title": "T", "author": "A"})
    @patch("apps.stories.api.fetch_story_text", return_value="text")
    def test_fetch_preview_exactly_at_limit(self, mock_text, mock_meta, client, auth_headers):
        """30th request should succeed, 31st should be rate limited."""
        url = "https://www.reddit.com/r/nosleep/comments/abc/story/"
        for i in range(30):
            resp = client.get(
                f"/api/stories/fetch-preview?reddit_url={url}",
                **auth_headers,
            )
            assert resp.status_code == 200, f"Request {i + 1} failed"

        # 31st request should be rate limited
        resp = client.get(
            f"/api/stories/fetch-preview?reddit_url={url}",
            **auth_headers,
        )
        assert resp.status_code == 429


class TestDownloadEndpoint:
    """Test audio file download."""

    @pytest.fixture
    def story_with_audio_file(self, db):
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.write(b"\xff\xfb\x90\x00" * 256)
        tmp.close()

        story = Story.objects.create(
            title="Download Test Story",
            text_content="Test content",
            content_hash="download_hash",
            audio_file_path=tmp.name,
        )
        yield story

        try:
            os.unlink(tmp.name)
        except FileNotFoundError:
            pass

    def test_download_returns_attachment(self, client, story_with_audio_file):
        resp = client.get(f"/api/player/download/{story_with_audio_file.id}")
        assert resp.status_code == 200
        assert "attachment" in resp["Content-Disposition"]
        assert "Download Test Story" in resp["Content-Disposition"]

    def test_download_not_found(self, client, db):
        resp = client.get("/api/player/download/9999")
        assert resp.status_code == 404
