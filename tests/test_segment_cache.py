"""Tests for the segment cache module, covering cache key computation and lookup."""

import os
import pytest
from unittest.mock import patch

from app.schemas.narration import ScriptSegment, SegmentType
from app.services.segment_cache import (
    compute_segment_cache_key,
    lookup,
    CacheLookupResult,
    SEGMENT_CACHE_DIR,
)


# ---------------------------------------------------------------------------
# compute_segment_cache_key — voice segments
# ---------------------------------------------------------------------------

class TestComputeKeyVoiceSegment:

    def test_includes_text_voice_and_preset(self):
        seg = ScriptSegment(
            type=SegmentType.NARRATION, character="narrator",
            text="The door creaked.", tone="ominous",
        )
        key = compute_segment_cache_key(seg, voice_id="voice-1", preset="horror_narrator")
        assert isinstance(key, str)
        assert len(key) == 16

    def test_different_text_produces_different_key(self):
        seg_a = ScriptSegment(type=SegmentType.NARRATION, character="narrator", text="Hello.")
        seg_b = ScriptSegment(type=SegmentType.NARRATION, character="narrator", text="Goodbye.")
        key_a = compute_segment_cache_key(seg_a, voice_id="v1", preset="p1")
        key_b = compute_segment_cache_key(seg_b, voice_id="v1", preset="p1")
        assert key_a != key_b

    def test_different_voice_id_produces_different_key(self):
        seg = ScriptSegment(type=SegmentType.NARRATION, character="narrator", text="Same text.")
        key_a = compute_segment_cache_key(seg, voice_id="voice-A", preset="horror_narrator")
        key_b = compute_segment_cache_key(seg, voice_id="voice-B", preset="horror_narrator")
        assert key_a != key_b

    def test_different_preset_produces_different_key(self):
        seg = ScriptSegment(type=SegmentType.NARRATION, character="narrator", text="Same text.")
        key_a = compute_segment_cache_key(seg, voice_id="v1", preset="horror_narrator")
        key_b = compute_segment_cache_key(seg, voice_id="v1", preset="whisper")
        assert key_a != key_b

    def test_dialogue_type_uses_same_voice_key_format(self):
        seg_narr = ScriptSegment(type=SegmentType.NARRATION, character="narrator", text="X.")
        seg_dial = ScriptSegment(type=SegmentType.DIALOGUE, character="narrator", text="X.")
        # Same text, voice, preset → same key (both are voice-type segments)
        key_narr = compute_segment_cache_key(seg_narr, voice_id="v1", preset="p1")
        key_dial = compute_segment_cache_key(seg_dial, voice_id="v1", preset="p1")
        assert key_narr == key_dial

    def test_same_inputs_produce_same_key(self):
        seg = ScriptSegment(type=SegmentType.NARRATION, character="narrator", text="Hello.")
        key_a = compute_segment_cache_key(seg, voice_id="v1", preset="horror_narrator")
        key_b = compute_segment_cache_key(seg, voice_id="v1", preset="horror_narrator")
        assert key_a == key_b


# ---------------------------------------------------------------------------
# compute_segment_cache_key — SFX segments
# ---------------------------------------------------------------------------

class TestComputeKeySfx:

    def test_sfx_key_includes_description(self):
        seg = ScriptSegment(type=SegmentType.SFX, description="door creaking")
        key = compute_segment_cache_key(seg)
        assert isinstance(key, str)
        assert len(key) == 16

    def test_different_description_produces_different_key(self):
        seg_a = ScriptSegment(type=SegmentType.SFX, description="door creaking")
        seg_b = ScriptSegment(type=SegmentType.SFX, description="glass shattering")
        assert compute_segment_cache_key(seg_a) != compute_segment_cache_key(seg_b)

    def test_case_insensitive_description(self):
        seg_a = ScriptSegment(type=SegmentType.SFX, description="Door Creaking")
        seg_b = ScriptSegment(type=SegmentType.SFX, description="door creaking")
        assert compute_segment_cache_key(seg_a) == compute_segment_cache_key(seg_b)

    def test_description_whitespace_normalized(self):
        seg_a = ScriptSegment(type=SegmentType.SFX, description="  door creaking  ")
        seg_b = ScriptSegment(type=SegmentType.SFX, description="door creaking")
        assert compute_segment_cache_key(seg_a) == compute_segment_cache_key(seg_b)


# ---------------------------------------------------------------------------
# compute_segment_cache_key — ambient segments
# ---------------------------------------------------------------------------

class TestComputeKeyAmbient:

    def test_ambient_key_includes_description(self):
        seg = ScriptSegment(type=SegmentType.AMBIENT, description="rain on roof")
        key = compute_segment_cache_key(seg)
        assert isinstance(key, str)
        assert len(key) == 16

    def test_loop_flag_changes_key(self):
        seg_no_loop = ScriptSegment(type=SegmentType.AMBIENT, description="rain", loop=False)
        seg_loop = ScriptSegment(type=SegmentType.AMBIENT, description="rain", loop=True)
        assert compute_segment_cache_key(seg_no_loop) != compute_segment_cache_key(seg_loop)

    def test_ambient_case_insensitive(self):
        seg_a = ScriptSegment(type=SegmentType.AMBIENT, description="Wind Howling")
        seg_b = ScriptSegment(type=SegmentType.AMBIENT, description="wind howling")
        assert compute_segment_cache_key(seg_a) == compute_segment_cache_key(seg_b)


# ---------------------------------------------------------------------------
# compute_segment_cache_key — pause segments
# ---------------------------------------------------------------------------

class TestComputeKeyPause:

    def test_pause_key_includes_duration(self):
        seg = ScriptSegment(type=SegmentType.PAUSE, duration_ms=2000)
        key = compute_segment_cache_key(seg)
        assert isinstance(key, str)
        assert len(key) == 16

    def test_different_duration_produces_different_key(self):
        seg_a = ScriptSegment(type=SegmentType.PAUSE, duration_ms=1000)
        seg_b = ScriptSegment(type=SegmentType.PAUSE, duration_ms=3000)
        assert compute_segment_cache_key(seg_a) != compute_segment_cache_key(seg_b)

    def test_none_duration_defaults_to_1500(self):
        seg_none = ScriptSegment(type=SegmentType.PAUSE, duration_ms=None)
        seg_1500 = ScriptSegment(type=SegmentType.PAUSE, duration_ms=1500)
        assert compute_segment_cache_key(seg_none) == compute_segment_cache_key(seg_1500)


# ---------------------------------------------------------------------------
# lookup — cache hit / miss
# ---------------------------------------------------------------------------

class TestLookup:

    def test_miss_when_no_file(self, tmp_path):
        with patch("app.services.segment_cache.SEGMENT_CACHE_DIR", str(tmp_path)):
            seg = ScriptSegment(type=SegmentType.PAUSE, duration_ms=1500)
            result = lookup(seg)
            assert not result.is_hit
            assert result.cached_path.startswith(str(tmp_path))
            assert result.cached_path.endswith(".mp3")

    def test_hit_when_file_exists(self, tmp_path):
        with patch("app.services.segment_cache.SEGMENT_CACHE_DIR", str(tmp_path)):
            seg = ScriptSegment(type=SegmentType.PAUSE, duration_ms=1500)
            # Compute the expected path and create the file
            key = compute_segment_cache_key(seg)
            cached_path = tmp_path / f"{key}.mp3"
            cached_path.write_bytes(b"fake audio data")

            result = lookup(seg)
            assert result.is_hit
            assert result.cached_path == str(cached_path)

    def test_returns_correct_cache_key(self, tmp_path):
        with patch("app.services.segment_cache.SEGMENT_CACHE_DIR", str(tmp_path)):
            seg = ScriptSegment(type=SegmentType.SFX, description="thunder")
            expected_key = compute_segment_cache_key(seg)
            result = lookup(seg)
            assert result.cache_key == expected_key

    def test_voice_lookup_passes_voice_id_and_preset(self, tmp_path):
        with patch("app.services.segment_cache.SEGMENT_CACHE_DIR", str(tmp_path)):
            seg = ScriptSegment(
                type=SegmentType.NARRATION, character="narrator",
                text="Hello.", tone="calm",
            )
            result = lookup(seg, voice_id="v1", preset="calm")
            expected_key = compute_segment_cache_key(seg, voice_id="v1", preset="calm")
            assert result.cache_key == expected_key
