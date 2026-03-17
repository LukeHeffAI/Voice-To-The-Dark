"""Tests for settings API endpoints."""

import json
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.stories.models import AppSetting


pytestmark = pytest.mark.django_db


class TestGetSettings:
    def test_get_settings(self, client, auth_headers):
        AppSetting.set("reddit_cache_ttl", "3600")
        resp = client.get("/api/settings/api", **auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["reddit_cache_ttl"] == "3600"

    def test_get_settings_defaults(self, client, auth_headers):
        resp = client.get("/api/settings/api", **auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["reddit_cache_ttl"] == "604800"  # default 1 week

    def test_get_settings_unauthenticated(self, client, db):
        resp = client.get("/api/settings/api")
        assert resp.status_code == 401


class TestUpdateSettings:
    def test_update_settings(self, client, auth_headers):
        resp = client.put(
            "/api/settings/api",
            data=json.dumps({"reddit_cache_ttl": 86400}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["updated"]["reddit_cache_ttl"] == "86400"
        assert AppSetting.get("reddit_cache_ttl") == "86400"

    def test_update_settings_invalid_ttl(self, client, auth_headers):
        resp = client.put(
            "/api/settings/api",
            data=json.dumps({"reddit_cache_ttl": 10}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 400

    def test_update_settings_ignores_unknown_keys(self, client, auth_headers):
        resp = client.put(
            "/api/settings/api",
            data=json.dumps({"unknown_key": "value"}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["updated"] == {}


class TestVoiceNotes:
    def test_get_voice_notes_empty(self, client, auth_headers):
        resp = client.get("/api/settings/voice-notes", **auth_headers)
        assert resp.status_code == 200
        assert resp.json() == {}

    @patch("apps.stories.settings_api.VOICE_POOL", [type("V", (), {"voice_id": "v1", "model": "m1"})()])
    def test_update_voice_notes(self, client, auth_headers):
        resp = client.put(
            "/api/settings/voice-notes",
            data=json.dumps({"v1": "Great for narration"}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["notes"]["v1"] == "Great for narration"

    def test_voice_notes_unauthenticated(self, client, db):
        resp = client.get("/api/settings/voice-notes")
        assert resp.status_code == 401


class TestVoicePreview:
    def test_voice_preview_not_in_pool(self, client, auth_headers):
        resp = client.get("/api/settings/voice-preview/nonexistent", **auth_headers)
        assert resp.status_code == 404


class TestUploadRedditCache:
    def _reddit_json(self, children=None):
        """Build a minimal Reddit listing JSON structure."""
        if children is None:
            children = [
                {
                    "data": {
                        "title": "Test Story",
                        "permalink": "/r/nosleep/comments/abc/test/",
                        "ups": 100,
                        "author": "test_author",
                        "id": "abc",
                    }
                }
            ]
        return {"data": {"children": children}}

    @patch("apps.stories.settings_api.get_cache_path_for_timeframe")
    def test_upload_valid_json(self, mock_cache_path, client, auth_headers, tmp_path):
        """POST valid Reddit JSON succeeds with 200 and correct posts_count."""
        mock_cache_path.return_value = tmp_path / "top.json"

        reddit_data = self._reddit_json()
        file = SimpleUploadedFile(
            "top.json",
            json.dumps(reddit_data).encode(),
            content_type="application/json",
        )
        resp = client.post(
            "/api/settings/upload-reddit-cache",
            {"timeframe": "alltime", "file": file},
            **auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["timeframe"] == "alltime"
        assert data["posts_count"] == 1

    def test_upload_invalid_timeframe(self, client, auth_headers):
        """An unrecognised timeframe returns 400."""
        file = SimpleUploadedFile(
            "top.json",
            json.dumps(self._reddit_json(children=[])).encode(),
            content_type="application/json",
        )
        resp = client.post(
            "/api/settings/upload-reddit-cache",
            {"timeframe": "invalid", "file": file},
            **auth_headers,
        )
        assert resp.status_code == 400

    def test_upload_invalid_json(self, client, auth_headers):
        """Non-JSON content returns 400."""
        file = SimpleUploadedFile(
            "top.json",
            b"not json at all",
            content_type="application/json",
        )
        resp = client.post(
            "/api/settings/upload-reddit-cache",
            {"timeframe": "alltime", "file": file},
            **auth_headers,
        )
        assert resp.status_code == 400

    def test_upload_wrong_structure(self, client, auth_headers):
        """JSON without a 'data' key returns 400."""
        file = SimpleUploadedFile(
            "top.json",
            json.dumps({"wrong": "structure"}).encode(),
            content_type="application/json",
        )
        resp = client.post(
            "/api/settings/upload-reddit-cache",
            {"timeframe": "alltime", "file": file},
            **auth_headers,
        )
        assert resp.status_code == 400

    def test_upload_requires_auth(self, client, db):
        """Unauthenticated upload returns 401."""
        file = SimpleUploadedFile(
            "top.json",
            json.dumps({"data": {"children": []}}).encode(),
            content_type="application/json",
        )
        resp = client.post(
            "/api/settings/upload-reddit-cache",
            {"timeframe": "alltime", "file": file},
        )
        assert resp.status_code == 401
