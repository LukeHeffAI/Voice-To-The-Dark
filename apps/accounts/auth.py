"""JWT authentication for Django Ninja.

Provides auth classes that support both Authorization header and cookie-based
authentication, matching the existing FastAPI behavior so tokens remain
compatible during migration.
"""

from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.http import HttpRequest
from jose import JWTError, jwt
from ninja.errors import HttpError
from ninja.security import HttpBearer

from apps.accounts.models import User


class _AnonymousMarker:
    """Truthy sentinel used by OptionalJWTAuth so Django Ninja doesn't reject the request."""

    def __bool__(self):
        return True


_ANONYMOUS = _AnonymousMarker()


def create_access_token(user_id: int, username: str) -> str:
    """Create a JWT access token matching the legacy format."""
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRE_HOURS)
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """Decode and validate a JWT. Returns the payload dict or None on failure."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


def _extract_token(request: HttpRequest) -> str | None:
    """Pull the JWT from the Authorization header or the auth_token cookie."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return request.COOKIES.get("auth_token")


class JWTAuth(HttpBearer):
    """Requires a valid JWT. Returns the User or raises 401."""

    def authenticate(self, request: HttpRequest, token: str | None = None) -> User:
        # HttpBearer extracts from Authorization header; also check cookie
        if not token:
            token = request.COOKIES.get("auth_token")
        if not token:
            raise HttpError(401, "Not authenticated")

        payload = decode_access_token(token)
        if not payload:
            raise HttpError(401, "Invalid or expired token")

        try:
            user = User.objects.get(id=int(payload["sub"]))
        except (User.DoesNotExist, KeyError, ValueError):
            raise HttpError(401, "User not found")

        return user


class OptionalJWTAuth(HttpBearer):
    """Returns the User if authenticated, a truthy sentinel otherwise.

    Endpoints using this auth should check ``isinstance(request.auth, User)``
    to distinguish authenticated users from anonymous requests.
    """

    def __call__(self, request: HttpRequest):
        token = _extract_token(request)
        if not token:
            return _ANONYMOUS  # truthy so Ninja doesn't 401

        payload = decode_access_token(token)
        if not payload:
            return _ANONYMOUS

        try:
            return User.objects.get(id=int(payload["sub"]))
        except (User.DoesNotExist, KeyError, ValueError):
            return _ANONYMOUS

    def authenticate(self, request: HttpRequest, token: str | None = None):
        # Not called — __call__ is overridden — but required by HttpBearer ABC.
        return _ANONYMOUS


def require_admin(request: HttpRequest) -> User:
    """Check that request.auth is an admin user. Raises 403 if not."""
    user = request.auth
    if not user or not user.is_admin:
        raise HttpError(403, "Admin access required")
    return user
