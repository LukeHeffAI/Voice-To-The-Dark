"""Tests for settings API endpoints."""

import json
from unittest.mock import patch

import pytest

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
