import logging

from django.conf import settings
from django.db import IntegrityError
from django.http import HttpResponse
from ninja import Router
from ninja.errors import HttpError

from apps.accounts.auth import JWTAuth, create_access_token, require_admin
from apps.accounts.models import User
from apps.accounts.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

logger = logging.getLogger(__name__)

router = Router(tags=["auth"])


@router.post("/register", response=UserResponse, auth=JWTAuth())
def register(request, payload: RegisterRequest):
    """Register a new user. Admin-only."""
    require_admin(request)

    username = payload.username.strip()
    password = payload.password

    if not username or len(username) < 3:
        raise HttpError(400, "Username must be at least 3 characters")
    if not password or len(password) < 6:
        raise HttpError(400, "Password must be at least 6 characters")

    if User.objects.filter(username=username).exists():
        raise HttpError(409, f"Username '{username}' is already taken")

    try:
        user = User.objects.create_user(username=username, password=password)
    except IntegrityError:
        raise HttpError(409, f"Username '{username}' is already taken")

    return user


@router.post("/login", response=TokenResponse)
def login(request, response: HttpResponse, payload: LoginRequest):
    """Authenticate and receive a JWT token."""
    user = User.objects.filter(username=payload.username).first()
    if not user or not user.check_password(payload.password):
        raise HttpError(401, "Invalid username or password")

    token = create_access_token(user.id, user.username)

    # Set the token as an httponly cookie for browser sessions
    response.set_cookie(
        "auth_token",
        token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="Lax",
        max_age=60 * 60 * 24 * 28,  # 4 weeks
    )

    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.post("/logout")
def logout(request, response: HttpResponse):
    """Log out by clearing the auth cookie."""
    response.delete_cookie("auth_token")
    return {"message": "Logged out"}


@router.get("/me", response=UserResponse, auth=JWTAuth())
def me(request):
    """Return the currently authenticated user."""
    return request.auth
