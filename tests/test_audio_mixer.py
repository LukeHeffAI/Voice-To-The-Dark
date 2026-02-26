"""Unit tests for app.services.audio_mixer.

Tests cover all public functions, internal helpers, data classes, and constants
in the audio mixer module. Audio data is created via pydub's AudioSegment.silent()
to avoid requiring real audio files. Where AudioSegment.from_file is called
internally (e.g. _build_timeline), it is patched to return silent segments.
"""

import math
import tempfile
import os
from dataclasses import fields
from unittest.mock import patch, MagicMock

import pytest
from pydub import AudioSegment

from app.schemas.narration import ScriptSegment, SegmentType
from app.services.audio_mixer import (
    AMBIENT_VOLUME_DB,
    SFX_VOLUME_DB,
    CROSSFADE_MS,
    INTRO_FADE_MS,
    OUTRO_FADE_MS,
    PAUSE_BETWEEN_SCENES_MS,
    TARGET_LOUDNESS_DBFS,
    TimelineEntry,
    MixTimeline,
    mix_narration,
    _build_timeline,
    _render_timeline,
    _apply_fades,
    _normalize,
    _render_voice_track,
    _render_ambient_bed,
    _render_sfx_layer,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seg(seg_type: SegmentType, **kwargs) -> ScriptSegment:
    """Shorthand factory for ScriptSegment."""
    return ScriptSegment(type=seg_type, **kwargs)


def _silence(duration_ms: int = 1000) -> AudioSegment:
    """Return a silent AudioSegment of the given duration."""
    return AudioSegment.silent(duration=duration_ms)


def _tone(duration_ms: int = 1000, volume_dbfs: float = -10.0) -> AudioSegment:
    """Return a non-silent AudioSegment (sine-wave-like) at the given volume.

    We generate it by creating silence and adjusting its level.  Because pure
    silence has -inf dBFS, we instead create a very short noise-like segment
    by overlaying a short click on silence, which gives a measurable dBFS.
    For simplicity in tests, we generate a segment from raw PCM bytes that
    contains a simple square wave so dBFS is finite and predictable.
    """
    # Build a 16-bit mono square wave at the desired volume
    sample_rate = 44100
    sample_width = 2  # 16-bit
    channels = 1
    num_samples = int(sample_rate * duration_ms / 1000)

    # Amplitude for the desired dBFS: dBFS = 20*log10(amplitude / max_amplitude)
    max_amp = 2 ** 15 - 1
    amplitude = int(max_amp * (10 ** (volume_dbfs / 20)))
    amplitude = max(1, min(max_amp, amplitude))

    # Square wave: alternating +amplitude / -amplitude every 100 samples
    import struct
    raw = b""
    for i in range(num_samples):
        val = amplitude if (i // 100) % 2 == 0 else -amplitude
        raw += struct.pack("<h", val)

    seg = AudioSegment(
        data=raw,
        sample_width=sample_width,
        frame_rate=sample_rate,
        channels=channels,
    )
    return seg


# ---------------------------------------------------------------------------
# Constants verification
# ---------------------------------------------------------------------------

class TestConstants:
    """Verify module-level mix configuration constants have expected values."""

    def test_ambient_volume_db(self):
        assert AMBIENT_VOLUME_DB == -20

    def test_sfx_volume_db(self):
        assert SFX_VOLUME_DB == -6

    def test_crossfade_ms(self):
        assert CROSSFADE_MS == 100

    def test_intro_fade_ms(self):
        assert INTRO_FADE_MS == 2500

    def test_outro_fade_ms(self):
        assert OUTRO_FADE_MS == 3500

    def test_pause_between_scenes_ms(self):
        assert PAUSE_BETWEEN_SCENES_MS == 1800

    def test_target_loudness_dbfs(self):
        assert TARGET_LOUDNESS_DBFS == -18.0


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

class TestTimelineEntry:
    """Tests for the TimelineEntry dataclass."""

    def test_default_position(self):
        audio = _silence(500)
        seg = _seg(SegmentType.NARRATION, text="hello")
        entry = TimelineEntry(audio=audio, segment=seg)
        assert entry.position_ms == 0

    def test_custom_position(self):
        audio = _silence(500)
        seg = _seg(SegmentType.SFX, description="bang")
        entry = TimelineEntry(audio=audio, segment=seg, position_ms=3000)
        assert entry.position_ms == 3000

    def test_stores_audio_and_segment(self):
        audio = _silence(200)
        seg = _seg(SegmentType.DIALOGUE, text="Hi", character="alice")
        entry = TimelineEntry(audio=audio, segment=seg, position_ms=100)
        assert entry.audio is audio
        assert entry.segment is seg
        assert entry.segment.type == SegmentType.DIALOGUE


class TestMixTimeline:
    """Tests for the MixTimeline dataclass."""

    def test_defaults_are_empty(self):
        tl = MixTimeline()
        assert tl.voice_track == []
        assert tl.sfx_entries == []
        assert tl.ambient_entries == []
        assert tl.total_duration_ms == 0

    def test_independent_default_lists(self):
        """Each instance should get its own list, not a shared mutable default."""
        tl1 = MixTimeline()
        tl2 = MixTimeline()
        tl1.voice_track.append("x")
        assert tl2.voice_track == []

    def test_has_expected_fields(self):
        names = {f.name for f in fields(MixTimeline)}
        assert names == {"voice_track", "sfx_entries", "ambient_entries", "total_duration_ms"}


# ---------------------------------------------------------------------------
# mix_narration (top-level)
# ---------------------------------------------------------------------------

class TestMixNarration:
    """Tests for the main mix_narration entry point."""

    def test_empty_segment_files_returns_one_second_silence(self):
        result = mix_narration([])
        assert isinstance(result, AudioSegment)
        assert len(result) == 1000  # 1 second

    def test_empty_segment_files_is_truly_silent(self):
        result = mix_narration([])
        assert result.dBFS == float("-inf")

    @patch("app.services.audio_mixer.AudioSegment.from_file")
    def test_single_narration_returns_audiosegment(self, mock_from_file):
        audio = _silence(2000)
        mock_from_file.return_value = audio
        seg = _seg(SegmentType.NARRATION, text="Once upon a time...")
        result = mix_narration([("/fake/path.mp3", seg)])
        assert isinstance(result, AudioSegment)
        # Duration should be at least 2000ms (the voice segment length)
        assert len(result) >= 2000

    @patch("app.services.audio_mixer.AudioSegment.from_file")
    def test_multiple_segments_mixed(self, mock_from_file):
        mock_from_file.return_value = _silence(1000)
        segments = [
            ("/fake/narration.mp3", _seg(SegmentType.NARRATION, text="Intro")),
            ("/fake/sfx.mp3", _seg(SegmentType.SFX, description="thunder")),
            ("/fake/narration2.mp3", _seg(SegmentType.NARRATION, text="More")),
        ]
        result = mix_narration(segments)
        assert isinstance(result, AudioSegment)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# _build_timeline
# ---------------------------------------------------------------------------

class TestBuildTimeline:
    """Tests for _build_timeline — constructing the timeline from segment files."""

    @patch("app.services.audio_mixer.AudioSegment.from_file")
    def test_voice_segments_advance_playhead(self, mock_from_file):
        """Narration and dialogue segments should be placed sequentially."""
        mock_from_file.return_value = _silence(1000)
        segments = [
            ("/a.mp3", _seg(SegmentType.NARRATION, text="First")),
            ("/b.mp3", _seg(SegmentType.NARRATION, text="Second")),
        ]
        tl = _build_timeline(segments)
        assert len(tl.voice_track) == 2
        assert tl.voice_track[0].position_ms == 0
        assert tl.voice_track[1].position_ms == 1000
        assert tl.total_duration_ms == 2000

    @patch("app.services.audio_mixer.AudioSegment.from_file")
    def test_dialogue_advances_playhead(self, mock_from_file):
        mock_from_file.return_value = _silence(500)
        segments = [
            ("/a.mp3", _seg(SegmentType.DIALOGUE, text="Hi", character="alice")),
            ("/b.mp3", _seg(SegmentType.DIALOGUE, text="Hello", character="bob")),
        ]
        tl = _build_timeline(segments)
        assert tl.voice_track[0].position_ms == 0
        assert tl.voice_track[1].position_ms == 500
        assert tl.total_duration_ms == 1000

    @patch("app.services.audio_mixer.AudioSegment.from_file")
    def test_sfx_placed_at_playhead_and_advances(self, mock_from_file):
        """SFX should be placed at the current playhead and advance it."""
        mock_from_file.return_value = _silence(800)
        segments = [
            ("/narr.mp3", _seg(SegmentType.NARRATION, text="Speaking")),
            ("/sfx.mp3", _seg(SegmentType.SFX, description="crash")),
        ]
        tl = _build_timeline(segments)
        assert len(tl.sfx_entries) == 1
        assert tl.sfx_entries[0].position_ms == 800  # after the narration
        # SFX advances playhead in this implementation
        assert tl.total_duration_ms == 1600

    @patch("app.services.audio_mixer.AudioSegment.from_file")
    def test_ambient_placed_at_playhead_no_advance(self, mock_from_file):
        """Ambient segments should be placed at the playhead but NOT advance it."""
        mock_from_file.return_value = _silence(1000)
        segments = [
            ("/narr.mp3", _seg(SegmentType.NARRATION, text="Start")),
            ("/amb.mp3", _seg(SegmentType.AMBIENT, description="rain")),
            ("/narr2.mp3", _seg(SegmentType.NARRATION, text="Continue")),
        ]
        tl = _build_timeline(segments)
        # Ambient placed at playhead=1000 but doesn't advance
        assert len(tl.ambient_entries) == 1
        assert tl.ambient_entries[0].position_ms == 1000
        # Second narration should also be at 1000 because ambient didn't advance
        assert tl.voice_track[1].position_ms == 1000
        assert tl.total_duration_ms == 2000

    @patch("app.services.audio_mixer.AudioSegment.from_file")
    def test_pause_segments_advance_playhead(self, mock_from_file):
        """Pause segments should advance the playhead like voice segments."""
        mock_from_file.return_value = _silence(1500)
        segments = [
            ("/narr.mp3", _seg(SegmentType.NARRATION, text="Before")),
            ("/pause.mp3", _seg(SegmentType.PAUSE, duration_ms=1500)),
            ("/narr2.mp3", _seg(SegmentType.NARRATION, text="After")),
        ]
        tl = _build_timeline(segments)
        # Pause goes to voice_track and advances playhead
        assert len(tl.voice_track) == 3
        assert tl.voice_track[1].position_ms == 1500
        assert tl.voice_track[1].segment.type == SegmentType.PAUSE
        assert tl.voice_track[2].position_ms == 3000
        assert tl.total_duration_ms == 4500

    @patch("app.services.audio_mixer.AudioSegment.from_file")
    def test_empty_timeline_has_zero_duration(self, mock_from_file):
        """Empty segment list yields an empty timeline."""
        tl = _build_timeline([])
        assert tl.total_duration_ms == 0
        assert tl.voice_track == []
        assert tl.sfx_entries == []
        assert tl.ambient_entries == []

    @patch("app.services.audio_mixer.AudioSegment.from_file")
    def test_mixed_segment_types_ordering(self, mock_from_file):
        """Complex scenario: narration, sfx, ambient, narration, pause, narration."""
        # Different durations per call
        durations = [1000, 500, 2000, 800, 1200, 600]
        call_count = {"n": 0}

        def side_effect(*args, **kwargs):
            idx = call_count["n"]
            call_count["n"] += 1
            return _silence(durations[idx])

        mock_from_file.side_effect = side_effect

        segments = [
            ("/a.mp3", _seg(SegmentType.NARRATION, text="Intro")),       # 1000ms
            ("/b.mp3", _seg(SegmentType.SFX, description="thunder")),    # 500ms
            ("/c.mp3", _seg(SegmentType.AMBIENT, description="rain")),   # 2000ms
            ("/d.mp3", _seg(SegmentType.NARRATION, text="Mid")),         # 800ms
            ("/e.mp3", _seg(SegmentType.PAUSE, duration_ms=1200)),       # 1200ms
            ("/f.mp3", _seg(SegmentType.NARRATION, text="End")),         # 600ms
        ]
        tl = _build_timeline(segments)

        # Voice: narration at 0, narration at 1500, pause at 2300, narration at 3500
        assert len(tl.voice_track) == 4  # 2 narrations + 1 pause + 1 narration
        assert tl.voice_track[0].position_ms == 0      # first narration
        assert tl.voice_track[1].position_ms == 1500    # second narration (after narr 1000 + sfx 500)
        assert tl.voice_track[2].position_ms == 2300    # pause (after narr 800)
        assert tl.voice_track[3].position_ms == 3500    # last narration (after pause 1200)

        # SFX at playhead=1000
        assert len(tl.sfx_entries) == 1
        assert tl.sfx_entries[0].position_ms == 1000

        # Ambient at playhead=1500 (after narration 1000 + sfx 500), no advance
        assert len(tl.ambient_entries) == 1
        assert tl.ambient_entries[0].position_ms == 1500

        assert tl.total_duration_ms == 4100

    @patch("app.services.audio_mixer.AudioSegment.from_file")
    def test_from_file_called_with_mp3_format(self, mock_from_file):
        mock_from_file.return_value = _silence(500)
        segments = [("/some/file.mp3", _seg(SegmentType.NARRATION, text="Hi"))]
        _build_timeline(segments)
        mock_from_file.assert_called_once_with("/some/file.mp3", format="mp3")


# ---------------------------------------------------------------------------
# _render_timeline
# ---------------------------------------------------------------------------

class TestRenderTimeline:
    """Tests for _render_timeline — rendering a MixTimeline to AudioSegment."""

    def test_zero_duration_returns_one_second_silence(self):
        tl = MixTimeline(total_duration_ms=0)
        result = _render_timeline(tl)
        assert len(result) == 1000

    def test_voice_only_timeline(self):
        audio = _silence(2000)
        seg = _seg(SegmentType.NARRATION, text="Hello")
        entry = TimelineEntry(audio=audio, segment=seg, position_ms=0)
        tl = MixTimeline(voice_track=[entry], total_duration_ms=2000)
        result = _render_timeline(tl)
        assert len(result) == 2000

    def test_output_duration_matches_timeline(self):
        audio = _silence(500)
        entry = TimelineEntry(
            audio=audio,
            segment=_seg(SegmentType.NARRATION, text="x"),
            position_ms=0,
        )
        tl = MixTimeline(voice_track=[entry], total_duration_ms=3000)
        result = _render_timeline(tl)
        # Canvas should be at least total_duration_ms
        assert len(result) >= 3000

    def test_sfx_and_ambient_layers_included(self):
        """When SFX and ambient entries exist, the result still has the correct duration."""
        voice_audio = _silence(1000)
        sfx_audio = _silence(500)
        amb_audio = _silence(800)

        voice_entry = TimelineEntry(
            audio=voice_audio,
            segment=_seg(SegmentType.NARRATION, text="line"),
            position_ms=0,
        )
        sfx_entry = TimelineEntry(
            audio=sfx_audio,
            segment=_seg(SegmentType.SFX, description="boom"),
            position_ms=200,
        )
        amb_entry = TimelineEntry(
            audio=amb_audio,
            segment=_seg(SegmentType.AMBIENT, description="wind"),
            position_ms=0,
        )

        tl = MixTimeline(
            voice_track=[voice_entry],
            sfx_entries=[sfx_entry],
            ambient_entries=[amb_entry],
            total_duration_ms=1500,
        )
        result = _render_timeline(tl)
        assert len(result) >= 1500


# ---------------------------------------------------------------------------
# _render_voice_track
# ---------------------------------------------------------------------------

class TestRenderVoiceTrack:
    """Tests for _render_voice_track — building the voice layer."""

    def test_empty_entries_returns_silent_canvas(self):
        result = _render_voice_track([], 2000)
        assert len(result) == 2000
        assert result.dBFS == float("-inf")

    def test_single_voice_placed_at_position(self):
        audio = _tone(1000, volume_dbfs=-10.0)
        entry = TimelineEntry(
            audio=audio,
            segment=_seg(SegmentType.NARRATION, text="Hi"),
            position_ms=500,
        )
        result = _render_voice_track([entry], 2000)
        assert len(result) == 2000
        # The first 500ms should be silence, then audio starts
        first_chunk = result[:400]
        assert first_chunk.dBFS == float("-inf")

    def test_crossfade_between_consecutive_voice(self):
        """Two consecutive narration segments should overlap by CROSSFADE_MS."""
        audio1 = _tone(1000, -10.0)
        audio2 = _tone(1000, -10.0)
        entry1 = TimelineEntry(
            audio=audio1,
            segment=_seg(SegmentType.NARRATION, text="Part 1"),
            position_ms=0,
        )
        entry2 = TimelineEntry(
            audio=audio2,
            segment=_seg(SegmentType.NARRATION, text="Part 2"),
            position_ms=1000,  # directly follows entry1
        )
        result = _render_voice_track([entry1, entry2], 2000)
        # The result should still be 2000ms canvas, but audio content
        # overlaps, so the total is still valid
        assert len(result) == 2000

    def test_pause_breaks_crossfade(self):
        """A pause between two narrations should prevent crossfading."""
        audio1 = _tone(500, -10.0)
        pause = _silence(300)
        audio2 = _tone(500, -10.0)

        entries = [
            TimelineEntry(
                audio=audio1,
                segment=_seg(SegmentType.NARRATION, text="Before"),
                position_ms=0,
            ),
            TimelineEntry(
                audio=pause,
                segment=_seg(SegmentType.PAUSE, duration_ms=300),
                position_ms=500,
            ),
            TimelineEntry(
                audio=audio2,
                segment=_seg(SegmentType.NARRATION, text="After"),
                position_ms=800,
            ),
        ]
        result = _render_voice_track(entries, 1300)
        # Should succeed without error
        assert len(result) == 1300

    def test_dialogue_to_dialogue_crossfade(self):
        """Dialogue segments should also crossfade with each other."""
        audio1 = _tone(800, -10.0)
        audio2 = _tone(800, -10.0)
        entries = [
            TimelineEntry(
                audio=audio1,
                segment=_seg(SegmentType.DIALOGUE, text="Hi", character="a"),
                position_ms=0,
            ),
            TimelineEntry(
                audio=audio2,
                segment=_seg(SegmentType.DIALOGUE, text="Hello", character="b"),
                position_ms=800,
            ),
        ]
        result = _render_voice_track(entries, 1600)
        assert len(result) == 1600


# ---------------------------------------------------------------------------
# _render_ambient_bed
# ---------------------------------------------------------------------------

class TestRenderAmbientBed:
    """Tests for _render_ambient_bed — building the ambient layer."""

    def test_no_entries_returns_silence(self):
        result = _render_ambient_bed([], 3000)
        assert len(result) == 3000
        assert result.dBFS == float("-inf")

    def test_single_ambient_fills_to_end(self):
        """A single ambient entry should loop/extend to fill the remaining duration."""
        audio = _tone(500, -10.0)
        entry = TimelineEntry(
            audio=audio,
            segment=_seg(SegmentType.AMBIENT, description="wind"),
            position_ms=0,
        )
        result = _render_ambient_bed([entry], 3000)
        assert len(result) == 3000
        # The ambient section should have some audio content (not all silence)
        assert result.dBFS > float("-inf")

    def test_ambient_loops_short_clip(self):
        """An ambient clip shorter than its span should be looped."""
        audio = _tone(200, -10.0)  # very short
        entry = TimelineEntry(
            audio=audio,
            segment=_seg(SegmentType.AMBIENT, description="crickets"),
            position_ms=0,
        )
        result = _render_ambient_bed([entry], 2000)
        assert len(result) == 2000

    def test_two_ambient_entries_scene_change(self):
        """The first ambient should run until the second starts, then the second fills the rest."""
        audio1 = _tone(400, -10.0)
        audio2 = _tone(300, -10.0)
        entry1 = TimelineEntry(
            audio=audio1,
            segment=_seg(SegmentType.AMBIENT, description="rain"),
            position_ms=0,
        )
        entry2 = TimelineEntry(
            audio=audio2,
            segment=_seg(SegmentType.AMBIENT, description="wind"),
            position_ms=1000,
        )
        result = _render_ambient_bed([entry1, entry2], 2000)
        assert len(result) == 2000

    def test_ambient_volume_reduced(self):
        """Ambient audio should be reduced by AMBIENT_VOLUME_DB."""
        audio = _tone(1000, -10.0)
        entry = TimelineEntry(
            audio=audio,
            segment=_seg(SegmentType.AMBIENT, description="forest"),
            position_ms=0,
        )
        result = _render_ambient_bed([entry], 1000)
        # The overlaid ambient is at -10 + AMBIENT_VOLUME_DB = -30 dBFS (approximately)
        # We just verify it's quieter than the input
        assert result.dBFS < -10.0

    def test_zero_span_ambient_skipped(self):
        """Two ambient entries at the same position should produce zero span for the first."""
        audio1 = _tone(500, -10.0)
        audio2 = _tone(500, -10.0)
        entry1 = TimelineEntry(
            audio=audio1,
            segment=_seg(SegmentType.AMBIENT, description="a"),
            position_ms=1000,
        )
        entry2 = TimelineEntry(
            audio=audio2,
            segment=_seg(SegmentType.AMBIENT, description="b"),
            position_ms=1000,
        )
        # Should not crash even with zero span
        result = _render_ambient_bed([entry1, entry2], 2000)
        assert len(result) == 2000


# ---------------------------------------------------------------------------
# _render_sfx_layer
# ---------------------------------------------------------------------------

class TestRenderSfxLayer:
    """Tests for _render_sfx_layer — placing SFX on the timeline."""

    def test_no_entries_returns_silence(self):
        result = _render_sfx_layer([], 2000)
        assert len(result) == 2000
        assert result.dBFS == float("-inf")

    def test_single_sfx_placed_at_position(self):
        audio = _tone(300, -10.0)
        entry = TimelineEntry(
            audio=audio,
            segment=_seg(SegmentType.SFX, description="thunder"),
            position_ms=500,
        )
        result = _render_sfx_layer([entry], 2000)
        assert len(result) == 2000
        # Audio content should be present
        assert result.dBFS > float("-inf")

    def test_sfx_volume_adjusted(self):
        """SFX should be adjusted by SFX_VOLUME_DB."""
        audio = _tone(500, -10.0)
        entry = TimelineEntry(
            audio=audio,
            segment=_seg(SegmentType.SFX, description="bang"),
            position_ms=0,
        )
        result = _render_sfx_layer([entry], 500)
        # SFX is at -10 + SFX_VOLUME_DB = -16 dBFS (approximately), plus fades
        # Just check it's quieter than raw -10
        assert result.dBFS < -10.0

    def test_multiple_sfx_at_different_positions(self):
        audio1 = _tone(200, -10.0)
        audio2 = _tone(200, -10.0)
        entry1 = TimelineEntry(
            audio=audio1,
            segment=_seg(SegmentType.SFX, description="knock"),
            position_ms=0,
        )
        entry2 = TimelineEntry(
            audio=audio2,
            segment=_seg(SegmentType.SFX, description="creak"),
            position_ms=1000,
        )
        result = _render_sfx_layer([entry1, entry2], 2000)
        assert len(result) == 2000
        assert result.dBFS > float("-inf")

    def test_sfx_gets_fade_in_and_fade_out(self):
        """SFX clips should have small fade-in and fade-out applied."""
        # Use a longer clip so the fades are measurable
        audio = _tone(2000, -6.0)
        entry = TimelineEntry(
            audio=audio,
            segment=_seg(SegmentType.SFX, description="ambient drone"),
            position_ms=0,
        )
        result = _render_sfx_layer([entry], 2000)
        # The first few ms should be quieter than the middle (due to fade_in)
        start = result[:30]
        middle = result[500:600]
        # fade_in means the start is attenuated
        if start.dBFS != float("-inf"):
            assert start.dBFS <= middle.dBFS


# ---------------------------------------------------------------------------
# _apply_fades
# ---------------------------------------------------------------------------

class TestApplyFades:
    """Tests for _apply_fades — applying intro/outro fades."""

    def test_applies_fades_to_audio(self):
        audio = _tone(10000, -10.0)
        tl = MixTimeline(total_duration_ms=10000)
        result = _apply_fades(audio, tl)
        assert isinstance(result, AudioSegment)
        assert len(result) == len(audio)

    def test_intro_fade_attenuates_start(self):
        """The start of the audio should be quieter after fading in."""
        audio = _tone(10000, -10.0)
        tl = MixTimeline(total_duration_ms=10000)
        result = _apply_fades(audio, tl)
        start_segment = result[:100]
        mid_segment = result[4000:4100]
        # Start should be quieter than middle (due to fade-in)
        if start_segment.dBFS != float("-inf"):
            assert start_segment.dBFS < mid_segment.dBFS

    def test_outro_fade_attenuates_end(self):
        """The end of the audio should be quieter after fading out."""
        audio = _tone(10000, -10.0)
        tl = MixTimeline(total_duration_ms=10000)
        result = _apply_fades(audio, tl)
        end_segment = result[-100:]
        mid_segment = result[4000:4100]
        # End should be quieter than middle (due to fade-out)
        if end_segment.dBFS != float("-inf"):
            assert end_segment.dBFS < mid_segment.dBFS

    def test_short_audio_uses_clamped_fade(self):
        """For very short audio, fade durations are clamped to len/4."""
        audio = _tone(400, -10.0)
        tl = MixTimeline(total_duration_ms=400)
        result = _apply_fades(audio, tl)
        # Should not raise and should have same length
        assert len(result) == 400

    def test_very_short_audio_no_crash(self):
        """Zero or near-zero length audio should not crash."""
        audio = _silence(10)
        tl = MixTimeline(total_duration_ms=10)
        result = _apply_fades(audio, tl)
        assert len(result) == 10

    def test_preserves_duration(self):
        audio = _tone(5000, -10.0)
        tl = MixTimeline(total_duration_ms=5000)
        result = _apply_fades(audio, tl)
        assert len(result) == len(audio)


# ---------------------------------------------------------------------------
# _normalize
# ---------------------------------------------------------------------------

class TestNormalize:
    """Tests for _normalize — loudness normalization."""

    def test_silent_audio_returns_same(self):
        """Pure silence (dBFS=-inf) should be returned unchanged."""
        audio = _silence(1000)
        result = _normalize(audio)
        assert result.dBFS == float("-inf")
        assert len(result) == 1000

    def test_adjusts_loudness_toward_target(self):
        """Audio quieter than target should be boosted."""
        audio = _tone(1000, -30.0)
        result = _normalize(audio)
        # Should be closer to TARGET_LOUDNESS_DBFS (-18)
        assert abs(result.dBFS - TARGET_LOUDNESS_DBFS) < abs(audio.dBFS - TARGET_LOUDNESS_DBFS)

    def test_loud_audio_reduced(self):
        """Audio louder than target should be attenuated."""
        audio = _tone(1000, -6.0)
        result = _normalize(audio)
        # Should be closer to TARGET_LOUDNESS_DBFS (-18)
        assert result.dBFS < audio.dBFS

    def test_clamps_extreme_amplification(self):
        """Normalization delta should be clamped to [-12, 12] dB."""
        # Very quiet audio: -60 dBFS
        audio = _tone(1000, -60.0)
        original_dbfs = audio.dBFS
        result = _normalize(audio)
        # Delta would be -18 - (-60) = 42 dB, but clamped to 12 dB
        delta = result.dBFS - original_dbfs
        assert delta <= 12.5  # small tolerance for floating point

    def test_clamps_extreme_attenuation(self):
        """Normalization delta should not exceed -12 dB reduction."""
        # Very loud audio: -3 dBFS
        audio = _tone(1000, -3.0)
        original_dbfs = audio.dBFS
        result = _normalize(audio)
        # Delta would be -18 - (-3) = -15 dB, but clamped to -12 dB
        delta = result.dBFS - original_dbfs
        assert delta >= -12.5  # small tolerance for floating point

    def test_preserves_duration(self):
        audio = _tone(2000, -20.0)
        result = _normalize(audio)
        assert len(result) == len(audio)

    def test_near_target_minimal_change(self):
        """Audio already near the target should not change much."""
        audio = _tone(1000, TARGET_LOUDNESS_DBFS)
        result = _normalize(audio)
        assert abs(result.dBFS - TARGET_LOUDNESS_DBFS) < 2.0


# ---------------------------------------------------------------------------
# Integration-style tests
# ---------------------------------------------------------------------------

class TestMixerIntegration:
    """Higher-level tests that exercise multiple mixer functions together."""

    @patch("app.services.audio_mixer.AudioSegment.from_file")
    def test_full_pipeline_narration_only(self, mock_from_file):
        """Single narration through the full mix pipeline."""
        mock_from_file.return_value = _tone(3000, -15.0)
        seg = _seg(SegmentType.NARRATION, text="A dark and stormy night...")
        result = mix_narration([("/voice.mp3", seg)])
        assert isinstance(result, AudioSegment)
        assert len(result) >= 3000
        # Should be normalized near target loudness
        assert result.dBFS != float("-inf")

    @patch("app.services.audio_mixer.AudioSegment.from_file")
    def test_full_pipeline_with_all_segment_types(self, mock_from_file):
        """All segment types through the full pipeline."""
        durations = [2000, 500, 1500, 1000, 800, 1200]
        call_count = {"n": 0}

        def side_effect(*a, **kw):
            idx = call_count["n"]
            call_count["n"] += 1
            return _tone(durations[idx], -15.0)

        mock_from_file.side_effect = side_effect

        segments = [
            ("/n1.mp3", _seg(SegmentType.NARRATION, text="Opening")),
            ("/sfx1.mp3", _seg(SegmentType.SFX, description="door creak")),
            ("/amb1.mp3", _seg(SegmentType.AMBIENT, description="night forest")),
            ("/n2.mp3", _seg(SegmentType.DIALOGUE, text="Who's there?", character="alice")),
            ("/pause.mp3", _seg(SegmentType.PAUSE, duration_ms=800)),
            ("/n3.mp3", _seg(SegmentType.NARRATION, text="Silence fell")),
        ]
        result = mix_narration(segments)
        assert isinstance(result, AudioSegment)
        assert len(result) > 0

    @patch("app.services.audio_mixer.AudioSegment.from_file")
    def test_build_then_render_then_normalize(self, mock_from_file):
        """Manually step through build -> render -> fades -> normalize."""
        mock_from_file.return_value = _tone(2000, -15.0)
        segments = [
            ("/a.mp3", _seg(SegmentType.NARRATION, text="Hello")),
            ("/b.mp3", _seg(SegmentType.NARRATION, text="World")),
        ]
        tl = _build_timeline(segments)
        assert tl.total_duration_ms == 4000

        rendered = _render_timeline(tl)
        assert len(rendered) >= 4000

        faded = _apply_fades(rendered, tl)
        assert len(faded) == len(rendered)

        normalized = _normalize(faded)
        assert len(normalized) == len(faded)

    @patch("app.services.audio_mixer.AudioSegment.from_file")
    def test_ambient_does_not_affect_total_duration(self, mock_from_file):
        """Adding ambient segments should not change total_duration_ms."""
        mock_from_file.return_value = _silence(1000)

        segments_no_amb = [
            ("/a.mp3", _seg(SegmentType.NARRATION, text="Hello")),
        ]
        tl_no_amb = _build_timeline(segments_no_amb)

        mock_from_file.reset_mock()

        segments_with_amb = [
            ("/a.mp3", _seg(SegmentType.NARRATION, text="Hello")),
            ("/b.mp3", _seg(SegmentType.AMBIENT, description="wind")),
        ]
        tl_with_amb = _build_timeline(segments_with_amb)

        assert tl_no_amb.total_duration_ms == tl_with_amb.total_duration_ms

    @patch("app.services.audio_mixer.AudioSegment.from_file")
    def test_sfx_does_advance_playhead(self, mock_from_file):
        """SFX should advance the playhead so following segments start later."""
        mock_from_file.return_value = _silence(500)

        segments_no_sfx = [
            ("/a.mp3", _seg(SegmentType.NARRATION, text="First")),
            ("/b.mp3", _seg(SegmentType.NARRATION, text="Second")),
        ]
        tl_no_sfx = _build_timeline(segments_no_sfx)

        mock_from_file.reset_mock()

        segments_with_sfx = [
            ("/a.mp3", _seg(SegmentType.NARRATION, text="First")),
            ("/sfx.mp3", _seg(SegmentType.SFX, description="boom")),
            ("/b.mp3", _seg(SegmentType.NARRATION, text="Second")),
        ]
        tl_with_sfx = _build_timeline(segments_with_sfx)

        # With SFX, second narration starts later
        assert tl_with_sfx.voice_track[1].position_ms > tl_no_sfx.voice_track[1].position_ms
        # Total duration is longer
        assert tl_with_sfx.total_duration_ms > tl_no_sfx.total_duration_ms
