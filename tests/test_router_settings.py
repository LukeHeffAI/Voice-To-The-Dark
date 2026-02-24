"""Tests for the /settings router endpoints."""

import json
import io
from app.models.app_setting import AppSetting


class TestSettingsPage:
    def test_redirects_to_login_when_unauthenticated(self, client, db_session):
        resp = client.get("/settings/")
        # Returns the login page HTML (200) since it renders login.html directly
        assert resp.status_code == 200
        assert "Sign" in resp.text

    def test_renders_for_authenticated_user(self, client, auth_headers, db_session):
        resp = client.get("/settings/", headers=auth_headers, cookies=_auth_cookie(auth_headers))
        assert resp.status_code == 200
        assert "Settings" in resp.text
        assert "Reddit Refresh Interval" in resp.text


class TestSettingsAPI:
    def test_get_settings_defaults(self, client, auth_headers, db_session):
        resp = client.get("/settings/api", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "reddit_cache_ttl" in data
        assert data["reddit_cache_ttl"] == "604800"

    def test_update_ttl(self, client, auth_headers, db_session):
        resp = client.put("/settings/api", json={
            "reddit_cache_ttl": "86400"
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["updated"]["reddit_cache_ttl"] == "86400"

        # Verify it persisted
        resp2 = client.get("/settings/api", headers=auth_headers)
        assert resp2.json()["reddit_cache_ttl"] == "86400"

    def test_update_ttl_rejects_invalid(self, client, auth_headers, db_session):
        resp = client.put("/settings/api", json={
            "reddit_cache_ttl": "not_a_number"
        }, headers=auth_headers)
        assert resp.status_code == 400

    def test_update_ttl_rejects_too_small(self, client, auth_headers, db_session):
        resp = client.put("/settings/api", json={
            "reddit_cache_ttl": "10"
        }, headers=auth_headers)
        assert resp.status_code == 400

    def test_ignores_unknown_keys(self, client, auth_headers, db_session):
        resp = client.put("/settings/api", json={
            "unknown_key": "value",
            "reddit_cache_ttl": "3600",
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert "unknown_key" not in resp.json()["updated"]
        assert resp.json()["updated"]["reddit_cache_ttl"] == "3600"

    def test_requires_auth(self, client, db_session):
        resp = client.get("/settings/api")
        assert resp.status_code == 401


class TestUploadRedditCache:
    def test_upload_valid_json(self, client, auth_headers, db_session):
        reddit_data = {
            "data": {
                "children": [
                    {"data": {"title": "Test Story", "permalink": "/r/nosleep/comments/abc/test/",
                              "ups": 100, "author": "test", "id": "abc"}}
                ]
            }
        }
        file_content = json.dumps(reddit_data).encode()

        resp = client.post("/settings/upload-reddit-cache",
            data={"timeframe": "alltime"},
            files={"file": ("top.json", io.BytesIO(file_content), "application/json")},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["posts_count"] == 1
        assert data["timeframe"] == "alltime"

    def test_upload_invalid_timeframe(self, client, auth_headers, db_session):
        file_content = json.dumps({"data": {"children": []}}).encode()
        resp = client.post("/settings/upload-reddit-cache",
            data={"timeframe": "invalid"},
            files={"file": ("top.json", io.BytesIO(file_content), "application/json")},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_upload_invalid_json(self, client, auth_headers, db_session):
        resp = client.post("/settings/upload-reddit-cache",
            data={"timeframe": "alltime"},
            files={"file": ("top.json", io.BytesIO(b"not json"), "application/json")},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_upload_wrong_structure(self, client, auth_headers, db_session):
        file_content = json.dumps({"wrong": "structure"}).encode()
        resp = client.post("/settings/upload-reddit-cache",
            data={"timeframe": "alltime"},
            files={"file": ("top.json", io.BytesIO(file_content), "application/json")},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_requires_auth(self, client, db_session):
        file_content = json.dumps({"data": {"children": []}}).encode()
        resp = client.post("/settings/upload-reddit-cache",
            data={"timeframe": "alltime"},
            files={"file": ("top.json", io.BytesIO(file_content), "application/json")},
        )
        assert resp.status_code == 401


def _auth_cookie(auth_headers: dict) -> dict:
    """Extract the token from auth headers and return it as a cookie dict."""
    token = auth_headers["Authorization"].replace("Bearer ", "")
    return {"auth_token": token}
