"""Tests for player API endpoints."""

import os
import tempfile

import pytest

from apps.stories.models import Story


pytestmark = pytest.mark.django_db


@pytest.fixture
def story_with_audio(db):
    """Create a story with an actual audio file on disk."""
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp.write(b"\xff\xfb\x90\x00" * 1000)  # Fake MP3 data
    tmp.close()

    story = Story.objects.create(
        title="Audio Story",
        text_content="Content",
        content_hash="audiohash",
        audio_file_path=tmp.name,
    )
    yield story

    # Cleanup
    if os.path.exists(tmp.name):
        os.unlink(tmp.name)


class TestStoryInfo:
    def test_story_info(self, client, test_story):
        resp = client.get(f"/api/player/story-info/{test_story.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == test_story.id
        assert data["title"] == "Test Horror Story"
        assert data["has_audio"] is False

    def test_story_info_not_found(self, client, db):
        resp = client.get("/api/player/story-info/9999")
        assert resp.status_code == 404


class TestStreamAudio:
    def test_stream_full(self, client, story_with_audio):
        resp = client.get(f"/api/player/stream/{story_with_audio.id}")
        assert resp.status_code == 200
        assert resp["Content-Type"] == "audio/mpeg"
        assert resp["Accept-Ranges"] == "bytes"

    def test_stream_range(self, client, story_with_audio):
        resp = client.get(
            f"/api/player/stream/{story_with_audio.id}",
            HTTP_RANGE="bytes=0-99",
        )
        assert resp.status_code == 206
        assert resp["Content-Range"].startswith("bytes 0-99/")
        assert resp["Content-Length"] == "100"

    def test_stream_no_audio(self, client, test_story):
        resp = client.get(f"/api/player/stream/{test_story.id}")
        assert resp.status_code == 404

    def test_stream_story_not_found(self, client, db):
        resp = client.get("/api/player/stream/9999")
        assert resp.status_code == 404


class TestDownloadAudio:
    def test_download(self, client, story_with_audio):
        resp = client.get(f"/api/player/download/{story_with_audio.id}")
        assert resp.status_code == 200
        assert "attachment" in resp["Content-Disposition"]
        assert "Audio Story" in resp["Content-Disposition"]

    def test_download_no_audio(self, client, test_story):
        resp = client.get(f"/api/player/download/{test_story.id}")
        assert resp.status_code == 404
