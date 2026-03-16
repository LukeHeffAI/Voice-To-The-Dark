"""JWT authentication for Django Ninja.

Provides Bearer token and cookie-based authentication,
matching the existing FastAPI auth system's token format.

Uses a minimal HMAC-based JWT implementation (HS256 only)
to avoid cryptography library dependencies.
"""

import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from django.conf import settings
from django.http import HttpRequest
from ninja.security import HttpBearer

from apps.accounts.models import User

logger = logging.getLogger(__name__)

# JWT configuration — matches FastAPI app/auth.py settings
JWT_SECRET_KEY = getattr(settings, "SECRET_KEY", "change_me_to_a_random_secret")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24 * 28  # 4 weeks


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def create_access_token(user: User) -> str:
    """Create a JWT token for the given user."""
    expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "exp": int(expire.timestamp()),
    }

    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = _b64url_encode(json.dumps(payload).encode())
    signing_input = f"{header}.{body}"
    signature = hmac.new(
        JWT_SECRET_KEY.encode(), signing_input.encode(), hashlib.sha256
    ).digest()
    sig = _b64url_encode(signature)

    return f"{header}.{body}.{sig}"


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    """Decode and validate a JWT. Returns the payload dict or None on failure."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None

        signing_input = f"{parts[0]}.{parts[1]}"
        expected_sig = hmac.new(
            JWT_SECRET_KEY.encode(), signing_input.encode(), hashlib.sha256
        ).digest()

        actual_sig = _b64url_decode(parts[2])
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        payload = json.loads(_b64url_decode(parts[1]))

        # Check expiration
        exp = payload.get("exp")
        if exp and time.time() > exp:
            return None

        return payload
    except Exception:
        return None


def _get_user_from_token(token: str) -> Optional[User]:
    """Validate a JWT token and return the corresponding User, or None."""
    payload = decode_access_token(token)
    if not payload:
        return None
    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError, TypeError):
        return None
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return None


class JWTAuth(HttpBearer):
    """Authenticate via Authorization: Bearer <token> header."""

    def authenticate(self, request: HttpRequest, token: str) -> Optional[User]:
        return _get_user_from_token(token)


class CookieAuth:
    """Authenticate via auth_token cookie."""

    openapi_type = "apiKey"
    param_name = "auth_token"

    def __call__(self, request: HttpRequest) -> Optional[User]:
        token = request.COOKIES.get("auth_token")
        if not token:
            return None
        return _get_user_from_token(token)


# Combined authenticator: tries Bearer header first, then cookie
jwt_auth = JWTAuth()
cookie_auth = CookieAuth()


def jwt_or_cookie(request: HttpRequest) -> Optional[User]:
    """Try Bearer header first, then cookie. Returns User or None."""
    # Try Authorization header
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        user = _get_user_from_token(token)
        if user:
            return user

    # Try cookie
    token = request.COOKIES.get("auth_token")
    if token:
        return _get_user_from_token(token)

    return None


def get_current_user(request: HttpRequest) -> User:
    """Get the authenticated user or raise 401."""
    from ninja.errors import HttpError

    user = jwt_or_cookie(request)
    if not user:
        raise HttpError(401, "Not authenticated")
    return user


def get_optional_user(request: HttpRequest) -> Optional[User]:
    """Get the authenticated user or None (no error)."""
    return jwt_or_cookie(request)


def require_admin(request: HttpRequest) -> User:
    """Get the authenticated user and require admin (is_staff) privileges."""
    from ninja.errors import HttpError

    user = get_current_user(request)
    if not user.is_staff:
        raise HttpError(403, "Admin access required")
    return user
