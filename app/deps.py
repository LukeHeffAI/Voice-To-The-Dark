"""FastAPI dependencies for authentication.

Provides two dependency functions:
- get_current_user: requires a valid JWT (raises 401 if missing/invalid)
- get_optional_user: returns the user if logged in, None otherwise
"""

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.story import User
from app.auth import decode_access_token


def _extract_token(request: Request) -> str | None:
    """Pull the JWT from the Authorization header or the auth_token cookie."""
    # Header first (for API clients)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]

    # Cookie fallback (for browser sessions)
    return request.cookies.get("auth_token")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Dependency that requires a valid authenticated user."""
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    """Dependency that returns the user if logged in, None otherwise."""
    token = _extract_token(request)
    if not token:
        return None

    payload = decode_access_token(token)
    if not payload:
        return None

    return db.query(User).filter(User.id == int(payload["sub"])).first()


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Dependency that requires admin privileges."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
