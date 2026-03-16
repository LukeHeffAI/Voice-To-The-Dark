"""Unit tests for services.winks."""

import math
import time
from unittest.mock import MagicMock, patch

import pytest

import services.winks as winks_module
from services.winks import (
    TOTAL_WINKS,
    _estimate_tts_chars,
    estimate_stories_winks,
    estimate_story_winks,
    get_subscription_info,
    get_winks_remaining,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_story(
    text_content="Some story text.",
    narration_text=None,
    voice_segments_texts=None,
    audio_file_path=None,
    story_id=1,
):
    """Build a mock story using the v2 ORM pattern.

    voice_segments_texts: list of text strings for voice segments.  When
    provided, the mock story.script.segments.filter() returns mock segment
    objects with those texts.  When None, story.script raises an exception
    (simulating a story without a script).
    """
    story = MagicMock()
    story.id = story_id
    story.text_content = text_content
    story.narration_text = narration_text
    story.audio_file_path = audio_file_path

    if voice_segments_texts is not None:
        # Build mock segments
        mock_segments = []
        for t in voice_segments_texts:
            seg = MagicMock()
            seg.text = t
            mock_segments.append(seg)

        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_segments
        mock_qs.__iter__ = lambda self: iter(mock_segments)

        mock_script = MagicMock()
        mock_script.segments = mock_qs

        story.script = mock_script
    else:
        # No script — accessing story.script raises an exception
        type(story).script = property(lambda self: (_ for _ in ()).throw(Exception("no script")))

    return story


def _reset_cache():
    """Reset the in-memory subscription cache between tests."""
    winks_module._cache["data"] = None
    winks_module._cache["expires_at"] = 0.0


# ---------------------------------------------------------------------------
# get_subscription_info: caching and failure behaviour
# ---------------------------------------------------------------------------

class TestGetSubscriptionInfo:

    def setup_method(self):
        _reset_cache()

    @patch("services.winks.settings")
    def test_returns_none_when_no_api_key(self, mock_settings):
        mock_settings.ELEVENLABS_API_KEY = None
        assert get_subscription_info() is None

    @patch("services.winks.settings")
    @patch("services.winks.requests.get")
    def test_returns_data_on_success(self, mock_get, mock_settings):
        mock_settings.ELEVENLABS_API_KEY = "test-key"
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"character_limit": 10000, "character_count": 2000}
        mock_get.return_value = mock_resp

        result = get_subscription_info()

        assert result == {"character_limit": 10000, "character_count": 2000}

    @patch("services.winks.settings")
    @patch("services.winks.requests.get")
    def test_caches_successful_response(self, mock_get, mock_settings):
        mock_settings.ELEVENLABS_API_KEY = "test-key"
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"character_limit": 10000, "character_count": 0}
        mock_get.return_value = mock_resp

        get_subscription_info()
        get_subscription_info()  # second call should use cache

        assert mock_get.call_count == 1

    @patch("services.winks.settings")
    @patch("services.winks.requests.get")
    def test_caches_failure_to_prevent_retry(self, mock_get, mock_settings):
        """A failed request should be cached so the next call within the
        failure TTL does not re-issue the HTTP request."""
        mock_settings.ELEVENLABS_API_KEY = "test-key"
        mock_get.side_effect = Exception("network error")

        result1 = get_subscription_info()
        result2 = get_subscription_info()  # should NOT trigger another request

        assert result1 is None
        assert result2 is None
        assert mock_get.call_count == 1

    @patch("services.winks.settings")
    @patch("services.winks.requests.get")
    def test_retries_after_failure_ttl_expires(self, mock_get, mock_settings):
        """After the failure TTL has passed, the function should retry."""
        mock_settings.ELEVENLABS_API_KEY = "test-key"
        mock_get.side_effect = Exception("network error")

        get_subscription_info()  # first failure — caches None

        # Expire the failure cache
        winks_module._cache["expires_at"] = time.time() - 1

        get_subscription_info()  # should retry

        assert mock_get.call_count == 2


# ---------------------------------------------------------------------------
# get_winks_remaining
# ---------------------------------------------------------------------------

class TestGetWinksRemaining:

    def setup_method(self):
        _reset_cache()

    @patch("services.winks.get_subscription_info", return_value=None)
    def test_returns_none_when_no_subscription_info(self, _):
        assert get_winks_remaining() is None

    @patch("services.winks.get_subscription_info", return_value={"character_limit": 0, "character_count": 0})
    def test_returns_none_when_character_limit_is_zero(self, _):
        assert get_winks_remaining() is None

    @patch(
        "services.winks.get_subscription_info",
        return_value={"character_limit": 10000, "character_count": 0},
    )
    def test_full_quota_returns_total_winks(self, _):
        remaining, total = get_winks_remaining()
        assert total == TOTAL_WINKS
        assert remaining == TOTAL_WINKS

    @patch(
        "services.winks.get_subscription_info",
        return_value={"character_limit": 10000, "character_count": 10000},
    )
    def test_exhausted_quota_returns_zero_remaining(self, _):
        remaining, total = get_winks_remaining()
        assert remaining == 0

    @patch(
        "services.winks.get_subscription_info",
        return_value={"character_limit": 10000, "character_count": 5000},
    )
    def test_half_quota_returns_half_winks(self, _):
        remaining, total = get_winks_remaining()
        # floor((10000-5000) * 40 / 10000) = floor(20.0) = 20
        assert remaining == 20
        assert total == TOTAL_WINKS

    @patch(
        "services.winks.get_subscription_info",
        return_value={"character_limit": 10000, "character_count": 15000},
    )
    def test_over_limit_clamped_to_zero(self, _):
        remaining, _ = get_winks_remaining()
        assert remaining == 0


# ---------------------------------------------------------------------------
# _estimate_tts_chars
# ---------------------------------------------------------------------------

class TestEstimateTtsChars:

    def test_uses_script_segments_when_available(self):
        story = _make_story(text_content="fallback", voice_segments_texts=["Hello.", "World."])
        result = _estimate_tts_chars(story)
        # "Hello." = 6, "World." = 6 → 12
        assert result == 12

    def test_falls_back_to_narration_text(self):
        story = _make_story(narration_text="narration here", text_content="raw text")
        result = _estimate_tts_chars(story)
        assert result == len("narration here")

    def test_falls_back_to_text_content_when_no_narration_text(self):
        story = _make_story(text_content="raw text")
        story.narration_text = None
        result = _estimate_tts_chars(story)
        assert result == len("raw text")

    def test_empty_story_returns_zero(self):
        story = _make_story(text_content="")
        story.narration_text = None
        result = _estimate_tts_chars(story)
        assert result == 0


# ---------------------------------------------------------------------------
# estimate_story_winks
# ---------------------------------------------------------------------------

class TestEstimateStoryWinks:

    def setup_method(self):
        _reset_cache()

    @patch("services.winks.get_subscription_info", return_value=None)
    def test_returns_none_when_no_subscription_info(self, _):
        story = _make_story(text_content="Some text.")
        assert estimate_story_winks(story) is None

    @patch(
        "services.winks.get_subscription_info",
        return_value={"character_limit": 10000, "character_count": 0},
    )
    def test_minimum_one_wink(self, _):
        """Even a very short story should cost at least 1 Wink."""
        story = _make_story(text_content="Hi")
        story.narration_text = None
        result = estimate_story_winks(story)
        assert result == 1

    @patch(
        "services.winks.get_subscription_info",
        return_value={"character_limit": 10000, "character_count": 0},
    )
    def test_cost_rounds_up(self, _):
        story = _make_story(text_content="A")
        story.narration_text = None
        result = estimate_story_winks(story)
        assert result == 1

    @patch(
        "services.winks.get_subscription_info",
        return_value={"character_limit": 10000, "character_count": 0},
    )
    def test_cost_proportional_to_text_length(self, _):
        # 2500 chars * 40 / 10000 = 10.0 → 10
        story = _make_story(text_content="A" * 2500)
        story.narration_text = None
        result = estimate_story_winks(story)
        assert result == 10

    @patch(
        "services.winks.get_subscription_info",
        return_value={"character_limit": 10000, "character_count": 0},
    )
    def test_returns_none_when_no_text(self, _):
        story = _make_story(text_content="")
        story.narration_text = None
        assert estimate_story_winks(story) is None


# ---------------------------------------------------------------------------
# estimate_stories_winks
# ---------------------------------------------------------------------------

class TestEstimateStoriesWinks:

    def setup_method(self):
        _reset_cache()

    @patch("services.winks.get_subscription_info", return_value=None)
    def test_returns_empty_dict_when_no_subscription_info(self, _):
        stories = [_make_story(text_content="text", story_id=1)]
        assert estimate_stories_winks(stories) == {}

    @patch(
        "services.winks.get_subscription_info",
        return_value={"character_limit": 10000, "character_count": 0},
    )
    def test_skips_stories_with_audio_file(self, _):
        s1 = _make_story(text_content="text", story_id=1, audio_file_path="/some/audio.mp3")
        s2 = _make_story(text_content="text", story_id=2, audio_file_path=None)
        s1.narration_text = None
        s2.narration_text = None

        result = estimate_stories_winks([s1, s2])

        assert 1 not in result
        assert 2 in result

    @patch(
        "services.winks.get_subscription_info",
        return_value={"character_limit": 10000, "character_count": 0},
    )
    def test_returns_dict_mapping_ids_to_costs(self, _):
        s1 = _make_story(text_content="A" * 2500, story_id=10)
        s2 = _make_story(text_content="A" * 5000, story_id=20)
        s1.narration_text = None
        s2.narration_text = None

        result = estimate_stories_winks([s1, s2])

        assert result[10] == 10  # ceil(2500*40/10000)
        assert result[20] == 20  # ceil(5000*40/10000)

    @patch(
        "services.winks.get_subscription_info",
        return_value={"character_limit": 10000, "character_count": 0},
    )
    def test_skips_stories_with_no_text(self, _):
        story = _make_story(text_content="", story_id=5)
        story.narration_text = None

        result = estimate_stories_winks([story])
        assert result == {}
