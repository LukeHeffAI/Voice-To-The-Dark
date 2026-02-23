"""Tests for the /auth router endpoints."""

import pytest
from app.auth import create_access_token


class TestLogin:
    def test_login_success(self, client, test_user):
        resp = client.post("/auth/login", json={
            "username": "testuser",
            "password": "testpass123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["token_type"] == "bearer"
        assert "access_token" in data
        assert data["user"]["username"] == "testuser"
        assert data["user"]["is_admin"] is False

    def test_login_sets_cookie(self, client, test_user):
        resp = client.post("/auth/login", json={
            "username": "testuser",
            "password": "testpass123",
        })
        assert resp.status_code == 200
        assert "auth_token" in resp.cookies

    def test_login_wrong_password(self, client, test_user):
        resp = client.post("/auth/login", json={
            "username": "testuser",
            "password": "wrongpass",
        })
        assert resp.status_code == 401
        assert "Invalid" in resp.json()["detail"]

    def test_login_nonexistent_user(self, client, db_session):
        resp = client.post("/auth/login", json={
            "username": "nobody",
            "password": "doesntmatter",
        })
        assert resp.status_code == 401


class TestLogout:
    def test_logout_clears_cookie(self, client):
        resp = client.post("/auth/logout")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Logged out"


class TestRegister:
    def test_admin_can_register_user(self, client, admin_headers, db_session):
        resp = client.post("/auth/register", json={
            "username": "newuser",
            "password": "newpass123",
        }, headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "newuser"
        assert data["is_admin"] is False

    def test_regular_user_cannot_register(self, client, auth_headers, db_session):
        resp = client.post("/auth/register", json={
            "username": "another",
            "password": "pass123",
        }, headers=auth_headers)
        assert resp.status_code == 403

    def test_unauthenticated_cannot_register(self, client, db_session):
        resp = client.post("/auth/register", json={
            "username": "another",
            "password": "pass123",
        })
        assert resp.status_code == 401

    def test_short_username_rejected(self, client, admin_headers, db_session):
        resp = client.post("/auth/register", json={
            "username": "ab",
            "password": "pass123",
        }, headers=admin_headers)
        assert resp.status_code == 400

    def test_short_password_rejected(self, client, admin_headers, db_session):
        resp = client.post("/auth/register", json={
            "username": "validname",
            "password": "short",
        }, headers=admin_headers)
        assert resp.status_code == 400

    def test_duplicate_username_rejected(self, client, admin_headers, test_user, db_session):
        resp = client.post("/auth/register", json={
            "username": "testuser",
            "password": "pass123456",
        }, headers=admin_headers)
        assert resp.status_code == 409


class TestGetMe:
    def test_returns_current_user(self, client, auth_headers, test_user):
        resp = client.get("/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "testuser"
        assert data["id"] == test_user.id

    def test_unauthenticated_rejected(self, client, db_session):
        resp = client.get("/auth/me")
        assert resp.status_code == 401

    def test_invalid_token_rejected(self, client, db_session):
        resp = client.get("/auth/me", headers={"Authorization": "Bearer garbage.token.here"})
        assert resp.status_code == 401
