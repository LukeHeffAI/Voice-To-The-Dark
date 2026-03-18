"""Tests for the /api/auth/ Django Ninja endpoints."""

import json

import pytest

from tests.conftest import post_json


@pytest.mark.django_db
class TestLogin:
    def test_login_success(self, api_client, test_user):
        resp = post_json(api_client, "/api/auth/login", {
            "username": "testuser",
            "password": "testpass123",
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data["token_type"] == "bearer"
        assert "access_token" in data
        assert data["user"]["username"] == "testuser"
        assert data["user"]["is_admin"] is False

    def test_login_sets_cookie(self, api_client, test_user):
        resp = post_json(api_client, "/api/auth/login", {
            "username": "testuser",
            "password": "testpass123",
        })
        assert resp.status_code == 200
        assert "auth_token" in resp.cookies

    def test_login_wrong_password(self, api_client, test_user):
        resp = post_json(api_client, "/api/auth/login", {
            "username": "testuser",
            "password": "wrongpass",
        })
        assert resp.status_code == 401
        data = json.loads(resp.content)
        assert "Invalid" in data["detail"]

    def test_login_nonexistent_user(self, api_client):
        resp = post_json(api_client, "/api/auth/login", {
            "username": "nobody",
            "password": "doesntmatter",
        })
        assert resp.status_code == 401


@pytest.mark.django_db
class TestLogout:
    def test_logout_clears_cookie(self, api_client):
        resp = api_client.post("/api/auth/logout", content_type="application/json")
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data["message"] == "Logged out"


@pytest.mark.django_db
class TestRegister:
    def test_admin_can_register_user(self, api_client, admin_headers):
        resp = post_json(api_client, "/api/auth/register", {
            "username": "newuser",
            "password": "newpass123",
        }, headers=admin_headers)
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data["username"] == "newuser"
        assert data["is_admin"] is False

    def test_regular_user_cannot_register(self, api_client, auth_headers):
        resp = post_json(api_client, "/api/auth/register", {
            "username": "another",
            "password": "pass123",
        }, headers=auth_headers)
        assert resp.status_code == 403

    def test_unauthenticated_cannot_register(self, api_client):
        resp = post_json(api_client, "/api/auth/register", {
            "username": "another",
            "password": "pass123",
        })
        assert resp.status_code == 401

    def test_short_username_rejected(self, api_client, admin_headers):
        resp = post_json(api_client, "/api/auth/register", {
            "username": "ab",
            "password": "pass123",
        }, headers=admin_headers)
        assert resp.status_code == 400

    def test_short_password_rejected(self, api_client, admin_headers):
        resp = post_json(api_client, "/api/auth/register", {
            "username": "validname",
            "password": "short",
        }, headers=admin_headers)
        assert resp.status_code == 400

    def test_duplicate_username_rejected(self, api_client, admin_headers, test_user):
        resp = post_json(api_client, "/api/auth/register", {
            "username": "testuser",
            "password": "pass123456",
        }, headers=admin_headers)
        assert resp.status_code == 409


@pytest.mark.django_db
class TestGetMe:
    def test_returns_current_user(self, api_client, auth_headers, test_user):
        resp = api_client.get("/api/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data["username"] == "testuser"
        assert data["id"] == test_user.id

    def test_unauthenticated_rejected(self, api_client):
        resp = api_client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_invalid_token_rejected(self, api_client):
        resp = api_client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer garbage.token.here"},
        )
        assert resp.status_code == 401
