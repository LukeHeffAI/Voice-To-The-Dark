import json
import logging
import math
import time

import requests
from django.conf import settings

from apps.audio.schemas import NarrationScript

logger = logging.getLogger(__name__)

TOTAL_WINKS = 40

# Simple in-memory cache for subscription info
_cache = {"data": None, "expires_at": 0.0}
_CACHE_TTL = 300  # 5 minutes
_FAILURE_TTL = 60  # 1-minute backoff when a request fails


def get_subscription_info() -> dict | None:
    """Fetch ElevenLabs subscription info, cached for 5 minutes.

    Failures are also cached for 1 minute to avoid hammering the upstream
    API (or blocking every page render) during outages.
    """
    now = time.time()
    if now < _cache["expires_at"]:
        return _cache["data"]  # may be None when a previous failure is cached

    if not settings.ELEVENLABS_API_KEY:
        return None

    try:
        resp = requests.get(
            "https://api.elevenlabs.io/v1/user/subscription",
            headers={"xi-api-key": settings.ELEVENLABS_API_KEY},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        _cache["data"] = data
        _cache["expires_at"] = now + _CACHE_TTL
        return data
    except Exception:
        logger.debug("Failed to fetch ElevenLabs subscription info", exc_info=True)
        _cache["data"] = None
        _cache["expires_at"] = now + _FAILURE_TTL
        return None


def get_winks_remaining() -> tuple[int, int] | None:
    """Return (remaining_winks, total_winks) or None if unavailable."""
    info = get_subscription_info()
    if not info:
        return None
    character_limit = info.get("character_limit", 0)
    if character_limit <= 0:
        return None
    character_count = info.get("character_count", 0)
    remaining = math.floor((character_limit - character_count) * TOTAL_WINKS / character_limit)
    remaining = max(0, min(remaining, TOTAL_WINKS))
    return (remaining, TOTAL_WINKS)


def _get_character_limit() -> int | None:
    """Get the character limit from cached subscription info."""
    info = get_subscription_info()
    if not info:
        return None
    limit = info.get("character_limit", 0)
    return limit if limit > 0 else None


def _estimate_tts_chars(story) -> int:
    """Estimate the number of TTS characters for a story."""
    if story.script_json:
        try:
            # Handle both str (legacy) and dict (Django JSONField) formats
            data = story.script_json
            if isinstance(data, str):
                data = json.loads(data)
            script = NarrationScript(**data)
            return sum(len(seg.text) for seg in script.voice_segments() if seg.text)
        except Exception:
            pass
    # Fallback to raw narration text
    return len(story.narration_text or story.text_content or "")


def estimate_story_winks(story) -> int | None:
    """Estimate Winks cost for a single story. Returns None if unavailable."""
    char_limit = _get_character_limit()
    if not char_limit:
        return None
    tts_chars = _estimate_tts_chars(story)
    if tts_chars <= 0:
        return None
    return max(1, math.ceil(tts_chars * TOTAL_WINKS / char_limit))


def estimate_stories_winks(stories) -> dict[int, int]:
    """Batch estimate Winks costs for a list of stories.

    Returns a dict mapping story.id -> winks_cost for stories without audio.
    """
    char_limit = _get_character_limit()
    if not char_limit:
        return {}
    result = {}
    for story in stories:
        if story.audio_file_path:
            continue
        tts_chars = _estimate_tts_chars(story)
        if tts_chars > 0:
            result[story.id] = max(1, math.ceil(tts_chars * TOTAL_WINKS / char_limit))
    return result
