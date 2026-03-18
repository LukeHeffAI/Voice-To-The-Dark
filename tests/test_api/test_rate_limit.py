"""Unit tests for apps.common.rate_limit."""

import time

import pytest
from ninja.errors import HttpError

from apps.common.rate_limit import _cleanup, _request_log, check_rate_limit


class TestCleanup:
    def test_removes_old_timestamps(self):
        user_id = 9999
        now = time.time()
        _request_log[user_id] = [now - 100, now - 50, now - 10, now - 1]
        _cleanup(user_id, window=30)
        # Only timestamps within the last 30 seconds should remain
        assert len(_request_log[user_id]) == 2
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


class TestCheckRateLimit:
    def setup_method(self):
        _request_log.clear()

    def teardown_method(self):
        _request_log.clear()

    def test_allows_requests_within_limit(self):
        for _ in range(5):
            check_rate_limit(1, max_requests=5, window_seconds=60)
        # 5 requests within limit of 5 should all succeed

    def test_raises_429_when_exceeded(self):
        for _ in range(5):
            check_rate_limit(1, max_requests=5, window_seconds=60)
        with pytest.raises(HttpError) as exc_info:
            check_rate_limit(1, max_requests=5, window_seconds=60)
        assert exc_info.value.status_code == 429

    def test_different_users_independent(self):
        for _ in range(5):
            check_rate_limit(1, max_requests=5, window_seconds=60)
        # User 2 should still be able to make requests
        check_rate_limit(2, max_requests=5, window_seconds=60)

    def test_expired_timestamps_cleaned(self):
        user_id = 3
        now = time.time()
        # Add old timestamps that should be expired
        _request_log[user_id] = [now - 120, now - 100, now - 80]
        # With a 60-second window, old timestamps should be cleaned
        check_rate_limit(user_id, max_requests=3, window_seconds=60)
        # Should succeed since old timestamps were cleaned
