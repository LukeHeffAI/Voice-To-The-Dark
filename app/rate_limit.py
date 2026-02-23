"""Lightweight in-memory rate limiter for expensive API endpoints.

Tracks request timestamps per user and rejects requests that exceed the
configured limit within the time window. State is lost on server restart,
which is acceptable for a personal-use project.
"""

import time
from collections import defaultdict
from fastapi import Depends, HTTPException, Request
from app.models.story import User
from app.deps import get_current_user

# Stores {user_id: [timestamp, timestamp, ...]}
_request_log: dict[int, list[float]] = defaultdict(list)


def _cleanup(user_id: int, window: float):
    """Remove timestamps older than the window."""
    cutoff = time.time() - window
    _request_log[user_id] = [t for t in _request_log[user_id] if t > cutoff]


def rate_limit(max_requests: int, window_seconds: float):
    """Create a rate-limit dependency.

    Usage:
        @router.post("/expensive")
        def endpoint(
            _: None = Depends(rate_limit(5, 3600)),
            user: User = Depends(get_current_user),
        ):
            ...

    Args:
        max_requests: Maximum allowed requests within the window.
        window_seconds: Window duration in seconds.
    """
    def dependency(request: Request, user: User = Depends(get_current_user)):
        _cleanup(user.id, window_seconds)

        if len(_request_log[user.id]) >= max_requests:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Maximum {max_requests} requests "
                       f"per {int(window_seconds // 60)} minutes.",
            )

        _request_log[user.id].append(time.time())

    return dependency
