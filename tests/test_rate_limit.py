"""Unit tests for app.rate_limit."""

import time
from unittest.mock import MagicMock, patch
from app.rate_limit import _cleanup, _request_log, rate_limit


class TestCleanup:
    def test_removes_old_timestamps(self):
        user_id = 9999
        now = time.time()
        _request_log[user_id] = [now - 100, now - 50, now - 10, now - 1]
        _cleanup(user_id, window=30)
        # Only timestamps within the last 30 seconds should remain
        assert len(_request_log[user_id]) == 2
        # Clean up
        del _request_log[user_id]

    def test_keeps_recent_timestamps(self):
        user_id = 9998
        now = time.time()
        _request_log[user_id] = [now - 1, now]
        _cleanup(user_id, window=60)
        assert len(_request_log[user_id]) == 2
        del _request_log[user_id]

    def test_handles_empty_log(self):
        user_id = 9997
        _request_log[user_id] = []
        _cleanup(user_id, window=60)
        assert _request_log[user_id] == []
        del _request_log[user_id]


class TestRateLimitDependency:
    def test_creates_callable_dependency(self):
        dep = rate_limit(5, 3600)
        assert callable(dep)
