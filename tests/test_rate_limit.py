"""Unit tests for apps.core.rate_limit."""

import time

from apps.core.rate_limit import _cleanup, _request_log, check_rate_limit


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


class TestCheckRateLimit:
    def test_allows_within_limit(self):
        user_id = 9996
        _request_log.pop(user_id, None)
        # Should not raise for first request
        check_rate_limit(user_id, max_requests=5, window_seconds=60)
        assert len(_request_log[user_id]) == 1
        del _request_log[user_id]

    def test_raises_when_exceeded(self):
        from ninja.errors import HttpError
        user_id = 9995
        _request_log[user_id] = [time.time()] * 5
        try:
            check_rate_limit(user_id, max_requests=5, window_seconds=60)
            assert False, "Should have raised HttpError"
        except HttpError as e:
            assert e.status_code == 429
        finally:
            del _request_log[user_id]
