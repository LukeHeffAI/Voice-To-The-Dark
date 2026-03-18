"""Tests for the /api/player/ Django Ninja endpoints."""

import json
import os
import tempfile

import pytest

from apps.stories.models import Story


@pytest.mark.django_db
class TestStoryInfo:
    def test_returns_story_info(self, api_client, sample_story):
        resp = api_client.get(f"/api/player/story-info/{sample_story.id}")
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data["id"] == sample_story.id
        assert data["title"] == "The Haunted House"
        assert data["has_audio"] is False

    def test_returns_has_audio_true(self, api_client, db):
        story = Story.objects.create(
            title="Audio Story",
            text_content="Content",
            content_hash="hash_audio",
            audio_file_path="/tmp/test.mp3",
        )
        resp = api_client.get(f"/api/player/story-info/{story.id}")
        assert resp.status_code == 200
        assert json.loads(resp.content)["has_audio"] is True

    def test_returns_404_for_missing(self, api_client, db):
        resp = api_client.get("/api/player/story-info/9999")
        assert resp.status_code == 404


@pytest.mark.django_db
class TestStreamAudio:
    def test_stream_returns_audio(self, api_client, db):
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"\x00" * 1024)
            audio_path = f.name
        try:
            story = Story.objects.create(
                title="Stream Test",
                text_content="Content",
                content_hash="hash_stream",
                audio_file_path=audio_path,
            )
            resp = api_client.get(f"/api/player/stream/{story.id}")
            assert resp.status_code == 200
            assert resp["Content-Type"] == "audio/mpeg"
            assert resp["Accept-Ranges"] == "bytes"
        finally:
            os.unlink(audio_path)

    def test_stream_range_request(self, api_client, db):
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"\x00" * 2048)
            audio_path = f.name
        try:
            story = Story.objects.create(
                title="Range Test",
                text_content="Content",
                content_hash="hash_range",
                audio_file_path=audio_path,
            )
            resp = api_client.get(
                f"/api/player/stream/{story.id}",
                headers={"Range": "bytes=0-511"},
            )
            assert resp.status_code == 206
            assert "Content-Range" in resp
            assert resp["Content-Length"] == "512"
        finally:
            os.unlink(audio_path)

    def test_stream_suffix_range(self, api_client, db):
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"\x00" * 2048)
            audio_path = f.name
        try:
            story = Story.objects.create(
                title="Suffix Range",
                text_content="Content",
                content_hash="hash_suffix_range",
                audio_file_path=audio_path,
            )
            resp = api_client.get(
                f"/api/player/stream/{story.id}",
                headers={"Range": "bytes=-500"},
            )
            assert resp.status_code == 206
            assert resp["Content-Length"] == "500"
        finally:
            os.unlink(audio_path)

    def test_stream_invalid_range_returns_416(self, api_client, db):
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"\x00" * 1024)
            audio_path = f.name
        try:
            story = Story.objects.create(
                title="Bad Range",
                text_content="Content",
                content_hash="hash_bad_range",
                audio_file_path=audio_path,
            )
            resp = api_client.get(
                f"/api/player/stream/{story.id}",
                headers={"Range": "bytes=5000-6000"},
            )
            assert resp.status_code == 416
            assert resp["Content-Range"] == "bytes */1024"
            assert resp["Accept-Ranges"] == "bytes"
        finally:
            os.unlink(audio_path)

    def test_stream_multi_range_returns_416(self, api_client, db):
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"\x00" * 1024)
            audio_path = f.name
        try:
            story = Story.objects.create(
                title="Multi Range",
                text_content="Content",
                content_hash="hash_multi_range",
                audio_file_path=audio_path,
            )
            resp = api_client.get(
                f"/api/player/stream/{story.id}",
                headers={"Range": "bytes=0-100,200-300"},
            )
            assert resp.status_code == 416
            assert resp["Content-Range"] == "bytes */1024"
        finally:
            os.unlink(audio_path)

    def test_stream_no_audio_returns_404(self, api_client, sample_story):
        resp = api_client.get(f"/api/player/stream/{sample_story.id}")
        assert resp.status_code == 404

    def test_stream_missing_file_returns_404(self, api_client, db):
        story = Story.objects.create(
            title="Missing File",
            text_content="Content",
            content_hash="hash_missing",
            audio_file_path="/nonexistent/path.mp3",
        )
        resp = api_client.get(f"/api/player/stream/{story.id}")
        assert resp.status_code == 404


@pytest.mark.django_db
class TestDownloadAudio:
    def test_download_returns_attachment(self, api_client, db):
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"\x00" * 512)
            audio_path = f.name
        try:
            story = Story.objects.create(
                title="Download Test",
                text_content="Content",
                content_hash="hash_download",
                audio_file_path=audio_path,
            )
            resp = api_client.get(f"/api/player/download/{story.id}")
            assert resp.status_code == 200
            assert "attachment" in resp["Content-Disposition"]
            assert "Download Test.mp3" in resp["Content-Disposition"]
        finally:
            os.unlink(audio_path)

    def test_download_no_audio_returns_404(self, api_client, sample_story):
        resp = api_client.get(f"/api/player/download/{sample_story.id}")
        assert resp.status_code == 404

    def test_download_missing_story_returns_404(self, api_client, db):
        resp = api_client.get("/api/player/download/9999")
        assert resp.status_code == 404
