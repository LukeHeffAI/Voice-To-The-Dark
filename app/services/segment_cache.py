"""Persistent cache for generated audio segments.

Segments are stored as content-addressable MP3 files in ./data/segment_cache/.
The cache key is a SHA-256 hash of the inputs that determine the audio output
(text, voice_id, preset for voice; description, duration for SFX/ambient;
duration_ms for pauses).
"""

import os
import hashlib
import logging
from dataclasses import dataclass

from app.schemas.narration import ScriptSegment, SegmentType

logger = logging.getLogger(__name__)

SEGMENT_CACHE_DIR = "./data/segment_cache"


@dataclass
class CacheLookupResult:
    """Result of checking the segment cache."""

    cache_key: str
    cached_path: str
    is_hit: bool


def compute_segment_cache_key(
    segment: ScriptSegment,
    voice_id: str | None = None,
    preset: str | None = None,
) -> str:
    """Compute a deterministic cache key for a merged segment.

    The key captures every input that affects the generated audio output,
    so any change to the segment content, voice, or preset produces a
    different key (cache miss).

    Args:
        segment: The (potentially merged) ScriptSegment.
        voice_id: Resolved ElevenLabs voice ID (required for voice segments).
        preset: Resolved ElevenLabs preset name (required for voice segments).

    Returns:
        A 16-character hex hash string.
    """
    if segment.type in (SegmentType.NARRATION, SegmentType.DIALOGUE):
        raw = f"voice|{segment.text or ''}|{voice_id or ''}|{preset or ''}"
    elif segment.type == SegmentType.SFX:
        raw = f"sfx|{(segment.description or '').lower().strip()}|5.0"
    elif segment.type == SegmentType.AMBIENT:
        duration = 10.0 if segment.loop else 5.0
        raw = f"ambient|{(segment.description or '').lower().strip()}|{duration}"
    elif segment.type == SegmentType.PAUSE:
        duration_ms = segment.duration_ms or 1500
        raw = f"pause|{duration_ms}"
    else:
        raw = f"unknown|{segment.type}"

    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def lookup(
    segment: ScriptSegment,
    voice_id: str | None = None,
    preset: str | None = None,
) -> CacheLookupResult:
    """Check whether a cached audio file exists for this segment.

    Returns a CacheLookupResult with is_hit=True if the file exists.
    The cached_path is always populated — it's the path where the file
    should be written if it doesn't exist yet.
    """
    cache_key = compute_segment_cache_key(segment, voice_id, preset)
    cached_path = os.path.join(SEGMENT_CACHE_DIR, f"{cache_key}.mp3")
    is_hit = os.path.exists(cached_path)

    if is_hit:
        logger.info("Segment cache HIT: %s (%s)", cache_key, segment.type.value)
    else:
        logger.info("Segment cache MISS: %s (%s)", cache_key, segment.type.value)

    return CacheLookupResult(
        cache_key=cache_key,
        cached_path=cached_path,
        is_hit=is_hit,
    )
