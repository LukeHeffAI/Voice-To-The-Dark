"""Auth API endpoints for Django Ninja.

Ported from app/routers/auth.py — register, login, logout, me.
"""

import logging

from django.contrib.auth import authenticate
from ninja import Router
from ninja.errors import HttpError

from apps.accounts.auth import create_access_token, get_current_user, require_admin
from apps.accounts.models import User
from schemas.story import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

logger = logging.getLogger(__name__)

router = Router()


@router.post("/register", response=UserResponse)
def register(request, payload: RegisterRequest):
    """Create a new user account. Admin only."""
    admin = require_admin(request)

    if len(payload.username) < 3:
        raise HttpError(400, "Username must be at least 3 characters")
    if len(payload.password) < 6:
        raise HttpError(400, "Password must be at least 6 characters")

    if User.objects.filter(username=payload.username).exists():
        raise HttpError(409, "Username already taken")

    user = User.objects.create_user(
        username=payload.username,
        password=payload.password,
    )

    logger.info("User created by %s: %s", admin.username, user.username)
    return UserResponse.from_user(user)


@router.post("/login", response=TokenResponse)
def login(request, payload: LoginRequest):
    """Authenticate and return an auth token."""
    user = authenticate(username=payload.username, password=payload.password)
    if not user:
        raise HttpError(401, "Invalid username or password")

    token = create_access_token(user)

    response_data = TokenResponse(
        access_token=token,
        user=UserResponse.from_user(user),
    )

    # Set the cookie on the response via request._ninja_response_cookie
    # Django Ninja doesn't have a direct response object in the handler,
    # so we store the cookie data for the middleware/post-processing
    request._auth_cookie = {
        "key": "auth_token",
        "value": token,
        "httponly": True,
        "samesite": "Lax",
        "max_age": 28 * 24 * 3600,
    }

    return response_data


@router.post("/logout")
def logout(request):
    """Clear the auth cookie."""
    request._delete_auth_cookie = True
    return {"message": "Logged out"}


@router.get("/me", response=UserResponse)
def get_me(request):
    """Return the currently authenticated user."""
    user = get_current_user(request)
    return UserResponse.from_user(user)
