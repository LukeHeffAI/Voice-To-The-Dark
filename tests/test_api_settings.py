"""Tests for the /api/settings/ Django Ninja endpoints."""

import io
import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.stories.models import AppSetting
from tests.conftest import post_json, put_json


@pytest.mark.django_db
class TestGetSettings:
    def test_get_settings_defaults(self, api_client, auth_headers):
        resp = api_client.get("/api/settings/", headers=auth_headers)
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert "reddit_cache_ttl" in data
        assert data["reddit_cache_ttl"] == "604800"

    def test_requires_auth(self, api_client):
        resp = api_client.get("/api/settings/")
        assert resp.status_code == 401


@pytest.mark.django_db
class TestUpdateSettings:
    def test_update_ttl(self, api_client, auth_headers):
        resp = put_json(api_client, "/api/settings/", {
            "reddit_cache_ttl": "86400",
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data["updated"]["reddit_cache_ttl"] == "86400"

        # Verify it persisted
        resp2 = api_client.get("/api/settings/", headers=auth_headers)
        data2 = json.loads(resp2.content)
        assert data2["reddit_cache_ttl"] == "86400"

    def test_update_ttl_rejects_invalid(self, api_client, auth_headers):
        resp = put_json(api_client, "/api/settings/", {
            "reddit_cache_ttl": "not_a_number",
        }, headers=auth_headers)
        assert resp.status_code == 400

    def test_update_ttl_rejects_too_small(self, api_client, auth_headers):
        resp = put_json(api_client, "/api/settings/", {
            "reddit_cache_ttl": "10",
        }, headers=auth_headers)
        assert resp.status_code == 400

    def test_ignores_unknown_keys(self, api_client, auth_headers):
        resp = put_json(api_client, "/api/settings/", {
            "unknown_key": "value",
            "reddit_cache_ttl": "3600",
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert "unknown_key" not in data["updated"]
        assert data["updated"]["reddit_cache_ttl"] == "3600"


@pytest.mark.django_db
class TestUploadRedditCache:
    def test_upload_valid_json(self, api_client, auth_headers):
        reddit_data = {
            "data": {
                "children": [
                    {"data": {"title": "Test Story", "permalink": "/r/nosleep/comments/abc/test/",
                              "ups": 100, "author": "test", "id": "abc"}}
                ]
            }
        }
        file_content = json.dumps(reddit_data).encode()
        resp = api_client.post(
            "/api/settings/upload-reddit-cache?timeframe=alltime",
            data={"file": SimpleUploadedFile("top.json", file_content, content_type="application/json")},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data["status"] == "ok"
        assert data["posts_count"] == 1
        assert data["timeframe"] == "alltime"

    def test_upload_invalid_timeframe(self, api_client, auth_headers):
        file_content = json.dumps({"data": {"children": []}}).encode()
        resp = api_client.post(
            "/api/settings/upload-reddit-cache?timeframe=invalid",
            data={"file": SimpleUploadedFile("top.json", file_content, content_type="application/json")},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_upload_invalid_json(self, api_client, auth_headers):
        resp = api_client.post(
            "/api/settings/upload-reddit-cache?timeframe=alltime",
            data={"file": SimpleUploadedFile("top.json", b"not json", content_type="application/json")},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_upload_wrong_structure(self, api_client, auth_headers):
        file_content = json.dumps({"wrong": "structure"}).encode()
        resp = api_client.post(
            "/api/settings/upload-reddit-cache?timeframe=alltime",
            data={"file": SimpleUploadedFile("top.json", file_content, content_type="application/json")},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_requires_auth(self, api_client):
        file_content = json.dumps({"data": {"children": []}}).encode()
        resp = api_client.post(
            "/api/settings/upload-reddit-cache?timeframe=alltime",
            data={"file": SimpleUploadedFile("top.json", file_content, content_type="application/json")},
        )
        assert resp.status_code == 401


@pytest.mark.django_db
class TestVoiceNotes:
    def test_get_voice_notes_empty(self, api_client, auth_headers):
        resp = api_client.get("/api/settings/voice-notes", headers=auth_headers)
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data == {}

    def test_get_voice_notes_requires_auth(self, api_client):
        resp = api_client.get("/api/settings/voice-notes")
        assert resp.status_code == 401

    def test_update_voice_notes_requires_auth(self, api_client):
        resp = put_json(api_client, "/api/settings/voice-notes", {"voice1": "note1"})
        assert resp.status_code == 401
