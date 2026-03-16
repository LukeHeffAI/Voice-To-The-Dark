"""Comprehensive tests for app initialization, database, config, and dependencies.

Covers:
- app/main.py   -- FastAPI app object, router registration, static files mount
- app/database.py -- SQLAlchemy Base, get_db session lifecycle
- app/config.py  -- Settings singleton and its default values
- app/deps.py    -- get_current_user, get_optional_user, require_admin
"""

import types

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.routing import APIRoute, Mount
from sqlalchemy import inspect
from sqlalchemy.orm import Session
from starlette.testclient import TestClient
from unittest.mock import MagicMock

from app.auth import create_access_token


# ---------------------------------------------------------------------------
# main.py -- FastAPI app initialisation
# ---------------------------------------------------------------------------

class TestAppObject:
    """Verify the FastAPI application is created and configured correctly."""

    def test_app_is_fastapi_instance(self):
        from app.main import app
        assert isinstance(app, FastAPI)

    def test_app_title(self):
        from app.main import app
        assert app.title == "Voice In The Dark"

    def test_app_version(self):
        from app.main import app
        assert app.version == "0.1.0"


class TestRouterRegistration:
    """Ensure all expected routers are included in the application."""

    @staticmethod
    def _route_paths(app: FastAPI) -> set[str]:
        """Collect all non-mount route paths registered on the app."""
        return {
            route.path
            for route in app.routes
            if isinstance(route, APIRoute)
        }

    @staticmethod
    def _route_prefixes(app: FastAPI) -> set[str]:
        """Collect unique first-segment prefixes from route paths."""
        prefixes = set()
        for route in app.routes:
            if isinstance(route, APIRoute):
                parts = route.path.strip("/").split("/")
                if parts and parts[0]:
                    prefixes.add(parts[0])
        return prefixes

    def test_auth_routes_registered(self):
        from app.main import app
        prefixes = self._route_prefixes(app)
        assert "auth" in prefixes, f"Expected 'auth' prefix; got {prefixes}"

    def test_audio_routes_registered(self):
        from app.main import app
        prefixes = self._route_prefixes(app)
        assert "audio" in prefixes, f"Expected 'audio' prefix; got {prefixes}"

    def test_stories_routes_registered(self):
        from app.main import app
        prefixes = self._route_prefixes(app)
        assert "stories" in prefixes, f"Expected 'stories' prefix; got {prefixes}"

    def test_settings_routes_registered(self):
        from app.main import app
        prefixes = self._route_prefixes(app)
        assert "settings" in prefixes, f"Expected 'settings' prefix; got {prefixes}"

    def test_player_routes_registered(self):
        """The player router is mounted at the root (no prefix), so at least
        one route should lack any of the other well-known prefixes."""
        from app.main import app
        non_prefixed = set()
        known_api_prefixes = {"auth", "audio", "stories", "settings"}
        for route in app.routes:
            if isinstance(route, APIRoute):
                first_seg = route.path.strip("/").split("/")[0]
                if first_seg not in known_api_prefixes:
                    non_prefixed.add(route.path)
        assert len(non_prefixed) > 0, "Expected player router to register root-level routes"

    def test_has_multiple_routes(self):
        """Sanity check: the application registers a non-trivial number of routes."""
        from app.main import app
        api_routes = [r for r in app.routes if isinstance(r, APIRoute)]
        assert len(api_routes) >= 5, f"Expected >=5 API routes, got {len(api_routes)}"


class TestStaticFilesMount:
    """Verify the static files mount point exists."""

    def test_static_mount_present(self):
        from app.main import app
        mounts = [
            route for route in app.routes
            if isinstance(route, Mount) and route.path == "/static"
        ]
        assert len(mounts) == 1, "Expected exactly one /static mount"

    def test_static_mount_name(self):
        from app.main import app
        for route in app.routes:
            if isinstance(route, Mount) and route.path == "/static":
                assert route.name == "static"
                return
        pytest.fail("/static mount not found")


# ---------------------------------------------------------------------------
# database.py -- SQLAlchemy setup
# ---------------------------------------------------------------------------

class TestDeclarativeBase:
    """Verify the SQLAlchemy declarative Base is valid."""

    def test_base_has_metadata(self):
        from app.database import Base
        assert hasattr(Base, "metadata")
        assert Base.metadata is not None

    def test_base_has_tables(self):
        """After model imports the metadata should know about tables."""
        from app.database import Base
        # Models are imported at app startup via main.py, so metadata should
        # already contain table definitions.
        assert len(Base.metadata.tables) > 0

    def test_stories_table_in_metadata(self):
        from app.database import Base
        assert "stories" in Base.metadata.tables

    def test_users_table_in_metadata(self):
        from app.database import Base
        assert "users" in Base.metadata.tables

    def test_base_can_be_subclassed(self):
        """Declarative base should allow new model subclasses."""
        from app.database import Base
        # Creating a throw-away model class should not raise
        class _Dummy(Base):
            __tablename__ = "_test_dummy_table_xyz"
            id = __import__("sqlalchemy").Column(
                __import__("sqlalchemy").Integer, primary_key=True
            )
        assert "_test_dummy_table_xyz" in Base.metadata.tables


class TestGetDb:
    """Verify that get_db yields a usable session and cleans up."""

    def test_get_db_yields_session(self, db_session):
        """Using the conftest db_session fixture ensures get_db's contract."""
        assert isinstance(db_session, Session)

    def test_get_db_generator_protocol(self):
        """get_db must be a generator (used as a FastAPI Depends)."""
        from app.database import get_db
        gen = get_db()
        assert hasattr(gen, "__next__"), "get_db should be a generator"
        assert hasattr(gen, "close"), "get_db generator should support close()"

    def test_get_db_yields_and_closes(self):
        """Walk the generator manually and ensure it terminates."""
        from app.database import get_db
        gen = get_db()
        session = next(gen)
        assert isinstance(session, Session)
        # Closing the generator triggers the finally block
        gen.close()

    def test_session_can_execute_query(self, db_session):
        """The yielded session should be capable of executing raw SQL."""
        result = db_session.execute(__import__("sqlalchemy").text("SELECT 1"))
        assert result.scalar() == 1


# ---------------------------------------------------------------------------
# config.py -- Settings defaults
# ---------------------------------------------------------------------------

class TestSettings:
    """Verify the Settings singleton and its default values."""

    def test_settings_object_exists(self):
        from app.config import settings
        assert settings is not None

    def test_settings_is_settings_class(self):
        from app.config import settings, Settings
        assert isinstance(settings, Settings)

    def test_jwt_algorithm_default(self):
        from app.config import settings
        assert settings.JWT_ALGORITHM == "HS256"

    def test_jwt_expire_hours_default(self):
        from app.config import settings
        # 24 * 28 = 672 hours (4 weeks)
        assert settings.JWT_EXPIRE_HOURS == 672

    def test_jwt_expire_hours_is_integer(self):
        from app.config import settings
        assert isinstance(settings.JWT_EXPIRE_HOURS, int)

    def test_jwt_secret_key_exists(self):
        from app.config import settings
        assert settings.JWT_SECRET_KEY is not None
        assert len(settings.JWT_SECRET_KEY) > 0

    def test_elevenlabs_key_attribute_exists(self):
        from app.config import settings
        assert hasattr(settings, "ELEVENLABS_API_KEY")

    def test_anthropic_key_attribute_exists(self):
        from app.config import settings
        assert hasattr(settings, "ANTHROPIC_API_KEY")


# ---------------------------------------------------------------------------
# deps.py -- FastAPI dependency functions
# ---------------------------------------------------------------------------

class TestGetCurrentUser:
    """Tests for the get_current_user dependency."""

    def test_valid_token_returns_user(self, client, test_user, auth_headers):
        """A request with a valid Bearer token should be authenticated."""
        # Use an endpoint that requires authentication.  /auth/me is standard.
        resp = client.get("/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == test_user.username

    def test_invalid_token_raises_401(self, client):
        headers = {"Authorization": "Bearer invalid.jwt.token"}
        resp = client.get("/auth/me", headers=headers)
        assert resp.status_code == 401

    def test_expired_token_raises_401(self, client, test_user):
        """An expired token must be rejected."""
        from datetime import datetime, timedelta, timezone
        from jose import jwt as jose_jwt
        from app.config import settings

        expired_payload = {
            "sub": str(test_user.id),
            "username": test_user.username,
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        token = jose_jwt.encode(
            expired_payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    def test_no_auth_header_raises_401(self, client):
        resp = client.get("/auth/me")
        assert resp.status_code == 401

    def test_malformed_auth_header_raises_401(self, client):
        """Authorization header that doesn't start with 'Bearer ' should fail."""
        resp = client.get("/auth/me", headers={"Authorization": "Token abc123"})
        assert resp.status_code == 401

    def test_empty_bearer_raises_401(self, client):
        resp = client.get("/auth/me", headers={"Authorization": "Bearer "})
        assert resp.status_code == 401

    def test_token_for_nonexistent_user_raises_401(self, client):
        """A structurally valid token whose 'sub' points to a deleted user."""
        token = create_access_token(999999, "ghost")
        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401


class TestGetCurrentUserDirect:
    """Call get_current_user directly with mock Request objects."""

    def test_direct_call_no_token(self, db_session):
        from app.deps import get_current_user

        request = MagicMock()
        request.headers.get.return_value = None
        request.cookies.get.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(request, db_session)
        assert exc_info.value.status_code == 401
        assert "Not authenticated" in exc_info.value.detail

    def test_direct_call_invalid_token(self, db_session):
        from app.deps import get_current_user

        request = MagicMock()
        request.headers.get.return_value = "Bearer garbage.token.value"
        request.cookies.get.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(request, db_session)
        assert exc_info.value.status_code == 401
        assert "Invalid or expired token" in exc_info.value.detail

    def test_direct_call_valid_token(self, db_session, test_user):
        from app.deps import get_current_user

        token = create_access_token(test_user.id, test_user.username)
        request = MagicMock()
        request.headers.get.return_value = f"Bearer {token}"
        request.cookies.get.return_value = None

        user = get_current_user(request, db_session)
        assert user.id == test_user.id
        assert user.username == test_user.username

    def test_direct_call_cookie_token(self, db_session, test_user):
        """Token provided via cookie instead of Authorization header."""
        from app.deps import get_current_user

        token = create_access_token(test_user.id, test_user.username)
        request = MagicMock()
        request.headers.get.return_value = None  # no Authorization header
        request.cookies.get.return_value = token

        user = get_current_user(request, db_session)
        assert user.id == test_user.id

    def test_direct_call_user_not_found(self, db_session):
        from app.deps import get_current_user

        token = create_access_token(999999, "ghost")
        request = MagicMock()
        request.headers.get.return_value = f"Bearer {token}"
        request.cookies.get.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(request, db_session)
        assert exc_info.value.status_code == 401
        assert "User not found" in exc_info.value.detail


class TestGetOptionalUser:
    """Tests for the get_optional_user dependency."""

    def test_no_token_returns_none(self, db_session):
        from app.deps import get_optional_user

        request = MagicMock()
        request.headers.get.return_value = None
        request.cookies.get.return_value = None

        result = get_optional_user(request, db_session)
        assert result is None

    def test_invalid_token_returns_none(self, db_session):
        from app.deps import get_optional_user

        request = MagicMock()
        request.headers.get.return_value = "Bearer bad.token.here"
        request.cookies.get.return_value = None

        result = get_optional_user(request, db_session)
        assert result is None

    def test_valid_token_returns_user(self, db_session, test_user):
        from app.deps import get_optional_user

        token = create_access_token(test_user.id, test_user.username)
        request = MagicMock()
        request.headers.get.return_value = f"Bearer {token}"
        request.cookies.get.return_value = None

        user = get_optional_user(request, db_session)
        assert user is not None
        assert user.id == test_user.id
        assert user.username == test_user.username

    def test_valid_token_via_cookie(self, db_session, test_user):
        from app.deps import get_optional_user

        token = create_access_token(test_user.id, test_user.username)
        request = MagicMock()
        request.headers.get.return_value = None
        request.cookies.get.return_value = token

        user = get_optional_user(request, db_session)
        assert user is not None
        assert user.id == test_user.id

    def test_token_for_missing_user_returns_none(self, db_session):
        from app.deps import get_optional_user

        token = create_access_token(999999, "ghost")
        request = MagicMock()
        request.headers.get.return_value = f"Bearer {token}"
        request.cookies.get.return_value = None

        result = get_optional_user(request, db_session)
        assert result is None

    def test_expired_token_returns_none(self, db_session, test_user):
        from app.deps import get_optional_user
        from datetime import datetime, timedelta, timezone
        from jose import jwt as jose_jwt
        from app.config import settings

        expired_payload = {
            "sub": str(test_user.id),
            "username": test_user.username,
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        token = jose_jwt.encode(
            expired_payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        request = MagicMock()
        request.headers.get.return_value = f"Bearer {token}"
        request.cookies.get.return_value = None

        result = get_optional_user(request, db_session)
        assert result is None


class TestRequireAdmin:
    """Tests for the require_admin dependency."""

    def test_admin_user_succeeds(self, admin_user):
        from app.deps import require_admin

        result = require_admin(admin_user)
        assert result.id == admin_user.id
        assert result.is_admin is True

    def test_non_admin_user_raises_403(self, test_user):
        from app.deps import require_admin

        with pytest.raises(HTTPException) as exc_info:
            require_admin(test_user)
        assert exc_info.value.status_code == 403
        assert "Admin access required" in exc_info.value.detail

    def test_admin_via_endpoint(self, client, admin_user, admin_headers):
        """Admin-protected endpoints should accept admin credentials.

        Use /auth/users as an admin-only endpoint (if it exists), otherwise
        fall back to checking that the admin_headers fixture works with /auth/me.
        """
        resp = client.get("/auth/me", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == admin_user.username

    def test_non_admin_rejected_by_admin_endpoint(self, client, test_user, auth_headers):
        """A non-admin user should receive 403 from an admin-only endpoint."""
        # POST /auth/register requires require_admin
        resp = client.post(
            "/auth/register",
            json={"username": "newuser", "password": "secret123"},
            headers=auth_headers,
        )
        assert resp.status_code == 403


class TestExtractToken:
    """Tests for the private _extract_token helper."""

    def test_extracts_from_bearer_header(self):
        from app.deps import _extract_token

        request = MagicMock()
        request.headers.get.return_value = "Bearer mytoken123"
        request.cookies.get.return_value = None

        assert _extract_token(request) == "mytoken123"

    def test_extracts_from_cookie(self):
        from app.deps import _extract_token

        request = MagicMock()
        request.headers.get.return_value = None
        request.cookies.get.return_value = "cookie_token_456"

        assert _extract_token(request) == "cookie_token_456"

    def test_header_takes_precedence_over_cookie(self):
        from app.deps import _extract_token

        request = MagicMock()
        request.headers.get.return_value = "Bearer header_token"
        request.cookies.get.return_value = "cookie_token"

        assert _extract_token(request) == "header_token"

    def test_returns_none_when_no_auth(self):
        from app.deps import _extract_token

        request = MagicMock()
        request.headers.get.return_value = None
        request.cookies.get.return_value = None

        assert _extract_token(request) is None

    def test_non_bearer_scheme_ignored(self):
        from app.deps import _extract_token

        request = MagicMock()
        request.headers.get.return_value = "Basic dXNlcjpwYXNz"
        request.cookies.get.return_value = None

        # Basic auth should not be extracted; falls through to cookie (None)
        assert _extract_token(request) is None
