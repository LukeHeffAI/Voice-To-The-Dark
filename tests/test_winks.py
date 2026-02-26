"""Unit tests for app.services.winks."""

import json
import math
import time
from unittest.mock import MagicMock, patch

import pytest

import app.services.winks as winks_module
from app.services.winks import (
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
    script_json=None,
    audio_file_path=None,
    story_id=1,
):
    story = MagicMock()
    story.id = story_id
    story.text_content = text_content
    story.narration_text = narration_text
    story.script_json = script_json
    story.audio_file_path = audio_file_path
    return story


def _make_script_json(segments):
    """Return a valid NarrationScript JSON string with given text segments."""
    return json.dumps({
        "title": "Test",
        "characters": {"narrator": {"voice_profile": "deep"}},
        "segments": [
            {"type": "narration", "character": "narrator", "text": t, "tone": "flat"}
            for t in segments
        ],
    })


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

    @patch("app.services.winks.settings")
    def test_returns_none_when_no_api_key(self, mock_settings):
        mock_settings.ELEVENLABS_API_KEY = None
        assert get_subscription_info() is None

    @patch("app.services.winks.settings")
    @patch("app.services.winks.requests.get")
    def test_returns_data_on_success(self, mock_get, mock_settings):
        mock_settings.ELEVENLABS_API_KEY = "test-key"
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"character_limit": 10000, "character_count": 2000}
        mock_get.return_value = mock_resp

        result = get_subscription_info()

        assert result == {"character_limit": 10000, "character_count": 2000}

    @patch("app.services.winks.settings")
    @patch("app.services.winks.requests.get")
    def test_caches_successful_response(self, mock_get, mock_settings):
        mock_settings.ELEVENLABS_API_KEY = "test-key"
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"character_limit": 10000, "character_count": 0}
        mock_get.return_value = mock_resp

        get_subscription_info()
        get_subscription_info()  # second call should use cache

        assert mock_get.call_count == 1

    @patch("app.services.winks.settings")
    @patch("app.services.winks.requests.get")
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

    @patch("app.services.winks.settings")
    @patch("app.services.winks.requests.get")
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

    @patch("app.services.winks.get_subscription_info", return_value=None)
    def test_returns_none_when_no_subscription_info(self, _):
        assert get_winks_remaining() is None

    @patch("app.services.winks.get_subscription_info", return_value={"character_limit": 0, "character_count": 0})
    def test_returns_none_when_character_limit_is_zero(self, _):
        assert get_winks_remaining() is None

    @patch(
        "app.services.winks.get_subscription_info",
        return_value={"character_limit": 10000, "character_count": 0},
    )
    def test_full_quota_returns_total_winks(self, _):
        remaining, total = get_winks_remaining()
        assert total == TOTAL_WINKS
        assert remaining == TOTAL_WINKS

    @patch(
        "app.services.winks.get_subscription_info",
        return_value={"character_limit": 10000, "character_count": 10000},
    )
    def test_exhausted_quota_returns_zero_remaining(self, _):
        remaining, total = get_winks_remaining()
        assert remaining == 0

    @patch(
        "app.services.winks.get_subscription_info",
        return_value={"character_limit": 10000, "character_count": 5000},
    )
    def test_half_quota_returns_half_winks(self, _):
        remaining, total = get_winks_remaining()
        # floor((10000-5000) * 40 / 10000) = floor(20.0) = 20
        assert remaining == 20
        assert total == TOTAL_WINKS

    @patch(
        "app.services.winks.get_subscription_info",
        return_value={"character_limit": 10000, "character_count": 15000},
    )
    def test_over_limit_clamped_to_zero(self, _):
        remaining, _ = get_winks_remaining()
        assert remaining == 0


# ---------------------------------------------------------------------------
# _estimate_tts_chars
# ---------------------------------------------------------------------------

class TestEstimateTtsChars:

    def test_uses_script_json_when_available(self):
        script = _make_script_json(["Hello.", "World."])
        story = _make_story(text_content="fallback", script_json=script)
        result = _estimate_tts_chars(story)
        # "Hello." = 6, "World." = 6 → 12
        assert result == 12

    def test_falls_back_to_narration_text(self):
        story = _make_story(narration_text="narration here", text_content="raw text")
        story.script_json = None
        result = _estimate_tts_chars(story)
        assert result == len("narration here")

    def test_falls_back_to_text_content_when_no_narration_text(self):
        story = _make_story(text_content="raw text")
        story.script_json = None
        story.narration_text = None
        result = _estimate_tts_chars(story)
        assert result == len("raw text")

    def test_invalid_script_json_falls_back_to_text(self):
        story = _make_story(text_content="raw text", script_json="not valid json {{")
        result = _estimate_tts_chars(story)
        assert result == len("raw text")

    def test_empty_story_returns_zero(self):
        story = _make_story(text_content="")
        story.script_json = None
        story.narration_text = None
        result = _estimate_tts_chars(story)
        assert result == 0

    def test_script_json_with_sfx_segments_excluded(self):
        """SFX/ambient segments should not be counted as TTS characters."""
        script_data = {
            "title": "Test",
            "characters": {"narrator": {"voice_profile": "deep"}},
            "segments": [
                {"type": "narration", "character": "narrator", "text": "Spoken.", "tone": "flat"},
                {"type": "sfx", "description": "door creak"},
            ],
        }
        story = _make_story(script_json=json.dumps(script_data))
        result = _estimate_tts_chars(story)
        assert result == len("Spoken.")


# ---------------------------------------------------------------------------
# estimate_story_winks
# ---------------------------------------------------------------------------

class TestEstimateStoryWinks:

    def setup_method(self):
        _reset_cache()

    @patch("app.services.winks.get_subscription_info", return_value=None)
    def test_returns_none_when_no_subscription_info(self, _):
        story = _make_story(text_content="Some text.")
        assert estimate_story_winks(story) is None

    @patch(
        "app.services.winks.get_subscription_info",
        return_value={"character_limit": 10000, "character_count": 0},
    )
    def test_minimum_one_wink(self, _):
        """Even a very short story should cost at least 1 Wink."""
        story = _make_story(text_content="Hi")
        story.script_json = None
        story.narration_text = None
        result = estimate_story_winks(story)
        assert result == 1

    @patch(
        "app.services.winks.get_subscription_info",
        return_value={"character_limit": 10000, "character_count": 0},
    )
    def test_cost_rounds_up(self, _):
        """ceil(tts_chars * 40 / char_limit) should be used for rounding."""
        # 1 char * 40 / 10000 = 0.004 → ceil = 1
        story = _make_story(text_content="A")
        story.script_json = None
        story.narration_text = None
        result = estimate_story_winks(story)
        assert result == 1

    @patch(
        "app.services.winks.get_subscription_info",
        return_value={"character_limit": 10000, "character_count": 0},
    )
    def test_cost_proportional_to_text_length(self, _):
        # 2500 chars * 40 / 10000 = 10.0 → 10
        story = _make_story(text_content="A" * 2500)
        story.script_json = None
        story.narration_text = None
        result = estimate_story_winks(story)
        assert result == 10

    @patch(
        "app.services.winks.get_subscription_info",
        return_value={"character_limit": 10000, "character_count": 0},
    )
    def test_returns_none_when_no_text(self, _):
        story = _make_story(text_content="")
        story.script_json = None
        story.narration_text = None
        assert estimate_story_winks(story) is None


# ---------------------------------------------------------------------------
# estimate_stories_winks
# ---------------------------------------------------------------------------

class TestEstimateStoriesWinks:

    def setup_method(self):
        _reset_cache()

    @patch("app.services.winks.get_subscription_info", return_value=None)
    def test_returns_empty_dict_when_no_subscription_info(self, _):
        stories = [_make_story(text_content="text", story_id=1)]
        assert estimate_stories_winks(stories) == {}

    @patch(
        "app.services.winks.get_subscription_info",
        return_value={"character_limit": 10000, "character_count": 0},
    )
    def test_skips_stories_with_audio_file(self, _):
        s1 = _make_story(text_content="text", story_id=1, audio_file_path="/some/audio.mp3")
        s2 = _make_story(text_content="text", story_id=2, audio_file_path=None)
        s1.script_json = None
        s1.narration_text = None
        s2.script_json = None
        s2.narration_text = None

        result = estimate_stories_winks([s1, s2])

        assert 1 not in result
        assert 2 in result

    @patch(
        "app.services.winks.get_subscription_info",
        return_value={"character_limit": 10000, "character_count": 0},
    )
    def test_returns_dict_mapping_ids_to_costs(self, _):
        s1 = _make_story(text_content="A" * 2500, story_id=10)
        s2 = _make_story(text_content="A" * 5000, story_id=20)
        s1.script_json = None
        s1.narration_text = None
        s2.script_json = None
        s2.narration_text = None

        result = estimate_stories_winks([s1, s2])

        assert result[10] == 10  # ceil(2500*40/10000)
        assert result[20] == 20  # ceil(5000*40/10000)

    @patch(
        "app.services.winks.get_subscription_info",
        return_value={"character_limit": 10000, "character_count": 0},
    )
    def test_skips_stories_with_no_text(self, _):
        story = _make_story(text_content="", story_id=5)
        story.script_json = None
        story.narration_text = None

        result = estimate_stories_winks([story])
        assert result == {}
