"""Lightweight in-memory rate limiter for Django Ninja endpoints.

Tracks request timestamps per user and rejects requests that exceed the
configured limit within the time window. State is lost on server restart,
which is acceptable for a personal-use project.
"""

import time
from collections import defaultdict

from ninja.errors import HttpError

# Stores {user_id: [timestamp, timestamp, ...]}
_request_log: dict[int, list[float]] = defaultdict(list)


def _cleanup(user_id: int, window: float):
    """Remove timestamps older than the window."""
    cutoff = time.time() - window
    _request_log[user_id] = [t for t in _request_log[user_id] if t > cutoff]


def check_rate_limit(user_id: int, max_requests: int, window_seconds: float):
    """Check rate limit for a user. Raises HttpError(429) if exceeded."""
    _cleanup(user_id, window_seconds)

    if len(_request_log[user_id]) >= max_requests:
        raise HttpError(
            429,
            f"Rate limit exceeded. Maximum {max_requests} requests "
            f"per {int(window_seconds // 60)} minutes.",
        )

    _request_log[user_id].append(time.time())
