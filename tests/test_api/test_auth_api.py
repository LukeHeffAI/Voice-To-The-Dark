"""Tests for auth API endpoints."""

import json

import pytest

from apps.accounts.auth import create_access_token, decode_access_token
from apps.accounts.models import User


pytestmark = pytest.mark.django_db


class TestRegister:
    def test_register_as_admin(self, client, admin_headers):
        resp = client.post(
            "/api/auth/register",
            data=json.dumps({"username": "newuser", "password": "pass123"}),
            content_type="application/json",
            **admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "newuser"
        assert data["is_admin"] is False
        assert User.objects.filter(username="newuser").exists()

    def test_register_requires_admin(self, client, auth_headers):
        resp = client.post(
            "/api/auth/register",
            data=json.dumps({"username": "newuser", "password": "pass123"}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 403

    def test_register_unauthenticated(self, client, db):
        resp = client.post(
            "/api/auth/register",
            data=json.dumps({"username": "newuser", "password": "pass123"}),
            content_type="application/json",
        )
        assert resp.status_code == 401

    def test_register_short_username(self, client, admin_headers):
        resp = client.post(
            "/api/auth/register",
            data=json.dumps({"username": "ab", "password": "pass123"}),
            content_type="application/json",
            **admin_headers,
        )
        assert resp.status_code == 400

    def test_register_short_password(self, client, admin_headers):
        resp = client.post(
            "/api/auth/register",
            data=json.dumps({"username": "newuser", "password": "short"}),
            content_type="application/json",
            **admin_headers,
        )
        assert resp.status_code == 400

    def test_register_duplicate_username(self, client, admin_headers, test_user):
        resp = client.post(
            "/api/auth/register",
            data=json.dumps({"username": "testuser", "password": "pass123"}),
            content_type="application/json",
            **admin_headers,
        )
        assert resp.status_code == 409


class TestLogin:
    def test_login_success(self, client, test_user):
        resp = client.post(
            "/api/auth/login",
            data=json.dumps({"username": "testuser", "password": "testpass123"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["user"]["username"] == "testuser"
        assert data["token_type"] == "bearer"

    def test_login_sets_cookie(self, client, test_user):
        resp = client.post(
            "/api/auth/login",
            data=json.dumps({"username": "testuser", "password": "testpass123"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert "auth_token" in resp.cookies

    def test_login_wrong_password(self, client, test_user):
        resp = client.post(
            "/api/auth/login",
            data=json.dumps({"username": "testuser", "password": "wrong"}),
            content_type="application/json",
        )
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client, db):
        resp = client.post(
            "/api/auth/login",
            data=json.dumps({"username": "ghost", "password": "pass123"}),
            content_type="application/json",
        )
        assert resp.status_code == 401


class TestLogout:
    def test_logout(self, client, db):
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Logged out"


class TestMe:
    def test_me_authenticated(self, client, test_user, auth_headers):
        resp = client.get("/api/auth/me", **auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "testuser"
        assert data["id"] == test_user.id

    def test_me_unauthenticated(self, client, db):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401


class TestJWTTokens:
    def test_create_and_decode_token(self, test_user):
        token = create_access_token(test_user)
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == str(test_user.id)
        assert payload["username"] == test_user.username

    def test_decode_invalid_token(self):
        assert decode_access_token("invalid.token.here") is None

    def test_decode_tampered_token(self, test_user):
        token = create_access_token(test_user)
        parts = token.split(".")
        parts[1] = parts[1] + "tampered"
        tampered = ".".join(parts)
        assert decode_access_token(tampered) is None
