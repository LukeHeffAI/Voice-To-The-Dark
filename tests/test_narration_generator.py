"""Tests for the narration generator service, covering tone-to-preset mapping,
individual segment generation, and the full generate_narration pipeline."""

import os
import pytest
from unittest.mock import MagicMock, patch, call

from pydub import AudioSegment

from app.schemas.narration import (
    NarrationScript,
    ScriptSegment,
    CharacterProfile,
    SegmentType,
)
from app.services.narration_generator import (
    generate_narration,
    _generate_segment,
    _tone_to_preset,
    _generate_voice_segment,
    _generate_sfx_segment,
    _generate_ambient_segment,
    _generate_pause_segment,
    DEFAULT_NARRATOR_VOICE,
    NarrationResult,
)
from app.services.segment_cache import CacheLookupResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_script(segments: list[ScriptSegment], title: str = "Test Story") -> NarrationScript:
    """Build a minimal NarrationScript for testing."""
    return NarrationScript(
        title=title,
        characters={
            "narrator": CharacterProfile(voice_profile="deep, steady, ominous"),
            "sarah": CharacterProfile(voice_profile="young, frightened"),
        },
        segments=segments,
    )


def _voice_map() -> dict[str, str]:
    return {
        "narrator": "voice-narrator-id",
        "sarah": "voice-sarah-id",
    }


# ---------------------------------------------------------------------------
# _tone_to_preset  (pure function -- no mocks needed)
# ---------------------------------------------------------------------------

class TestToneToPreset:

    def test_none_returns_horror_narrator(self):
        assert _tone_to_preset(None) == "horror_narrator"

    def test_empty_string_returns_horror_narrator(self):
        assert _tone_to_preset("") == "horror_narrator"

    def test_whisper_quietly(self):
        assert _tone_to_preset("whisper quietly") == "whisper"

    def test_quiet_keyword(self):
        assert _tone_to_preset("quiet and eerie") == "whisper"

    def test_hushed_keyword(self):
        assert _tone_to_preset("hushed tones") == "whisper"

    def test_soft_keyword(self):
        assert _tone_to_preset("soft and gentle") == "whisper"

    def test_calm_and_steady(self):
        assert _tone_to_preset("calm and steady") == "calm"

    def test_composed_keyword(self):
        assert _tone_to_preset("composed delivery") == "calm"

    def test_matter_of_fact_keyword(self):
        assert _tone_to_preset("matter-of-fact") == "calm"

    def test_panic_and_scream(self):
        assert _tone_to_preset("panic and scream") == "horror_dialogue"

    def test_frantic_keyword(self):
        assert _tone_to_preset("frantic, desperate") == "horror_dialogue"

    def test_terrified_keyword(self):
        assert _tone_to_preset("terrified whisper") == "horror_dialogue"
        # "terrified" is checked first (high-intensity cues take priority)

    def test_shout_keyword(self):
        assert _tone_to_preset("shout loudly") == "horror_dialogue"

    def test_desperate_keyword(self):
        assert _tone_to_preset("desperate plea") == "horror_dialogue"

    def test_ominous_dark_returns_default(self):
        assert _tone_to_preset("ominous, dark") == "horror_narrator"

    def test_foreboding_returns_default(self):
        assert _tone_to_preset("foreboding") == "horror_narrator"

    def test_case_insensitive(self):
        assert _tone_to_preset("WHISPER") == "whisper"
        assert _tone_to_preset("CALM") == "calm"
        assert _tone_to_preset("PANIC") == "horror_dialogue"

    def test_mixed_case(self):
        assert _tone_to_preset("Quiet Whisper") == "whisper"


# ---------------------------------------------------------------------------
# _generate_segment  (dispatch tests — now uses output_path directly)
# ---------------------------------------------------------------------------

class TestGenerateSegment:

    @patch("app.services.narration_generator.generate_audio")
    def test_dispatches_narration_to_voice(self, mock_gen_audio):
        segment = ScriptSegment(
            type=SegmentType.NARRATION,
            character="narrator",
            text="It was a dark night.",
            tone="ominous",
        )
        result = _generate_segment(segment, _voice_map(), "/cache/abc123.mp3")
        assert result == "/cache/abc123.mp3"
        mock_gen_audio.assert_called_once_with(
            "It was a dark night.",
            "voice-narrator-id",
            output_path="/cache/abc123.mp3",
            preset="horror_narrator",
        )

    @patch("app.services.narration_generator.generate_audio")
    def test_dispatches_dialogue_to_voice(self, mock_gen_audio):
        segment = ScriptSegment(
            type=SegmentType.DIALOGUE,
            character="sarah",
            text="Who's there?",
            tone="whisper quietly",
        )
        result = _generate_segment(segment, _voice_map(), "/cache/def456.mp3")
        assert result == "/cache/def456.mp3"
        mock_gen_audio.assert_called_once_with(
            "Who's there?",
            "voice-sarah-id",
            output_path="/cache/def456.mp3",
            preset="whisper",
        )

    @patch("app.services.narration_generator.generate_sfx")
    def test_dispatches_sfx(self, mock_gen_sfx):
        segment = ScriptSegment(
            type=SegmentType.SFX,
            description="door creaking slowly",
        )
        result = _generate_segment(segment, _voice_map(), "/cache/sfx123.mp3")
        assert result == "/cache/sfx123.mp3"
        mock_gen_sfx.assert_called_once_with(
            "door creaking slowly",
            output_path="/cache/sfx123.mp3",
            duration_seconds=5.0,
        )

    @patch("app.services.narration_generator.generate_sfx")
    def test_dispatches_ambient(self, mock_gen_sfx):
        segment = ScriptSegment(
            type=SegmentType.AMBIENT,
            description="rain on a tin roof",
            loop=False,
        )
        result = _generate_segment(segment, _voice_map(), "/cache/amb123.mp3")
        assert result == "/cache/amb123.mp3"
        mock_gen_sfx.assert_called_once_with(
            "rain on a tin roof",
            output_path="/cache/amb123.mp3",
            duration_seconds=5.0,
        )

    @patch("app.services.narration_generator.generate_sfx")
    def test_ambient_with_loop_uses_longer_duration(self, mock_gen_sfx):
        segment = ScriptSegment(
            type=SegmentType.AMBIENT,
            description="wind howling",
            loop=True,
        )
        result = _generate_segment(segment, _voice_map(), "/cache/amb456.mp3")
        assert result == "/cache/amb456.mp3"
        mock_gen_sfx.assert_called_once_with(
            "wind howling",
            output_path="/cache/amb456.mp3",
            duration_seconds=10.0,
        )

    @patch("app.services.narration_generator.AudioSegment")
    def test_dispatches_pause(self, mock_audio_cls):
        mock_silence = MagicMock()
        mock_audio_cls.silent.return_value = mock_silence

        segment = ScriptSegment(
            type=SegmentType.PAUSE,
            duration_ms=2000,
        )
        result = _generate_segment(segment, _voice_map(), "/cache/pause123.mp3")
        assert result == "/cache/pause123.mp3"
        mock_audio_cls.silent.assert_called_once_with(duration=2000)
        mock_silence.export.assert_called_once_with(
            "/cache/pause123.mp3", format="mp3"
        )

    @patch("app.services.narration_generator.AudioSegment")
    def test_pause_default_duration(self, mock_audio_cls):
        mock_silence = MagicMock()
        mock_audio_cls.silent.return_value = mock_silence

        segment = ScriptSegment(
            type=SegmentType.PAUSE,
            duration_ms=None,
        )
        _generate_segment(segment, _voice_map(), "/cache/pause_default.mp3")
        mock_audio_cls.silent.assert_called_once_with(duration=1500)


# ---------------------------------------------------------------------------
# _generate_segment  (empty/missing content -> None)
# ---------------------------------------------------------------------------

class TestGenerateSegmentReturnsNone:

    @patch("app.services.narration_generator.generate_audio")
    def test_narration_with_empty_text_returns_none(self, mock_gen_audio):
        segment = ScriptSegment(
            type=SegmentType.NARRATION,
            character="narrator",
            text="",
        )
        assert _generate_segment(segment, _voice_map(), "/cache/x.mp3") is None
        mock_gen_audio.assert_not_called()

    @patch("app.services.narration_generator.generate_audio")
    def test_narration_with_none_text_returns_none(self, mock_gen_audio):
        segment = ScriptSegment(
            type=SegmentType.NARRATION,
            character="narrator",
            text=None,
        )
        assert _generate_segment(segment, _voice_map(), "/cache/x.mp3") is None
        mock_gen_audio.assert_not_called()

    @patch("app.services.narration_generator.generate_audio")
    def test_dialogue_with_empty_text_returns_none(self, mock_gen_audio):
        segment = ScriptSegment(
            type=SegmentType.DIALOGUE,
            character="sarah",
            text="",
        )
        assert _generate_segment(segment, _voice_map(), "/cache/x.mp3") is None
        mock_gen_audio.assert_not_called()

    @patch("app.services.narration_generator.generate_sfx")
    def test_sfx_with_empty_description_returns_none(self, mock_gen_sfx):
        segment = ScriptSegment(
            type=SegmentType.SFX,
            description="",
        )
        assert _generate_segment(segment, _voice_map(), "/cache/x.mp3") is None
        mock_gen_sfx.assert_not_called()

    @patch("app.services.narration_generator.generate_sfx")
    def test_sfx_with_none_description_returns_none(self, mock_gen_sfx):
        segment = ScriptSegment(
            type=SegmentType.SFX,
            description=None,
        )
        assert _generate_segment(segment, _voice_map(), "/cache/x.mp3") is None
        mock_gen_sfx.assert_not_called()

    @patch("app.services.narration_generator.generate_sfx")
    def test_ambient_with_empty_description_returns_none(self, mock_gen_sfx):
        segment = ScriptSegment(
            type=SegmentType.AMBIENT,
            description="",
        )
        assert _generate_segment(segment, _voice_map(), "/cache/x.mp3") is None
        mock_gen_sfx.assert_not_called()

    @patch("app.services.narration_generator.generate_sfx")
    def test_ambient_with_none_description_returns_none(self, mock_gen_sfx):
        segment = ScriptSegment(
            type=SegmentType.AMBIENT,
            description=None,
        )
        assert _generate_segment(segment, _voice_map(), "/cache/x.mp3") is None
        mock_gen_sfx.assert_not_called()


# ---------------------------------------------------------------------------
# _generate_voice_segment  (voice-map fallback behaviour)
# ---------------------------------------------------------------------------

class TestVoiceSegmentVoiceMapping:

    @patch("app.services.narration_generator.generate_audio")
    def test_uses_character_voice_from_map(self, mock_gen_audio):
        segment = ScriptSegment(
            type=SegmentType.DIALOGUE,
            character="sarah",
            text="Hello",
        )
        _generate_voice_segment(segment, _voice_map(), "/cache/x.mp3")
        mock_gen_audio.assert_called_once()
        assert mock_gen_audio.call_args.args[1] == "voice-sarah-id"

    @patch("app.services.narration_generator.generate_audio")
    def test_falls_back_to_narrator_when_character_missing(self, mock_gen_audio):
        segment = ScriptSegment(
            type=SegmentType.DIALOGUE,
            character="unknown_char",
            text="Hello",
        )
        _generate_voice_segment(segment, _voice_map(), "/cache/x.mp3")
        mock_gen_audio.assert_called_once()
        assert mock_gen_audio.call_args.args[1] == "voice-narrator-id"

    @patch("app.services.narration_generator.generate_audio")
    def test_falls_back_to_default_when_no_narrator_in_map(self, mock_gen_audio):
        segment = ScriptSegment(
            type=SegmentType.DIALOGUE,
            character="unknown_char",
            text="Hello",
        )
        _generate_voice_segment(segment, {"other": "other-id"}, "/cache/x.mp3")
        mock_gen_audio.assert_called_once()
        assert mock_gen_audio.call_args.args[1] == DEFAULT_NARRATOR_VOICE

    @patch("app.services.narration_generator.generate_audio")
    def test_none_character_defaults_to_narrator_key(self, mock_gen_audio):
        segment = ScriptSegment(
            type=SegmentType.NARRATION,
            character=None,
            text="Something ominous.",
        )
        _generate_voice_segment(segment, _voice_map(), "/cache/x.mp3")
        mock_gen_audio.assert_called_once()
        assert mock_gen_audio.call_args.args[1] == "voice-narrator-id"


# ---------------------------------------------------------------------------
# generate_narration  (full pipeline)
# ---------------------------------------------------------------------------

class TestGenerateNarration:

    @patch("app.services.narration_generator.os.makedirs")
    @patch("app.services.narration_generator.cache_lookup")
    @patch("app.services.narration_generator.mix_narration")
    @patch("app.services.narration_generator.generate_sfx")
    @patch("app.services.narration_generator.generate_audio")
    def test_full_pipeline_returns_narration_result(
        self,
        mock_gen_audio,
        mock_gen_sfx,
        mock_mix,
        mock_cache_lookup,
        mock_makedirs,
    ):
        mock_final = MagicMock(spec=AudioSegment)
        mock_mix.return_value = mock_final

        # All cache misses
        mock_cache_lookup.return_value = CacheLookupResult(
            cache_key="abc", cached_path="/cache/abc.mp3", is_hit=False,
        )

        segments = [
            ScriptSegment(type=SegmentType.NARRATION, character="narrator",
                          text="The door opened.", tone="ominous"),
            ScriptSegment(type=SegmentType.SFX, description="door creaking"),
        ]
        script = _make_script(segments)

        result = generate_narration(script, _voice_map(), "/output/story.mp3")

        assert isinstance(result, NarrationResult)
        assert result.output_path == "/output/story.mp3"
        assert result.total_segments == 2
        assert result.cache_misses == 2
        assert result.cache_hits == 0
        mock_gen_audio.assert_called_once()
        mock_gen_sfx.assert_called_once()
        mock_mix.assert_called_once()
        mock_final.export.assert_called_once_with("/output/story.mp3", format="mp3")

    @patch("app.services.narration_generator.os.makedirs")
    @patch("app.services.narration_generator.cache_lookup")
    @patch("app.services.narration_generator.mix_narration")
    @patch("app.services.narration_generator.generate_audio")
    def test_auto_generates_output_path_when_none(
        self,
        mock_gen_audio,
        mock_mix,
        mock_cache_lookup,
        mock_makedirs,
    ):
        mock_mix.return_value = MagicMock(spec=AudioSegment)
        mock_cache_lookup.return_value = CacheLookupResult(
            cache_key="abc", cached_path="/cache/abc.mp3", is_hit=False,
        )

        segments = [
            ScriptSegment(type=SegmentType.NARRATION, character="narrator",
                          text="Hello.", tone=None),
        ]
        script = _make_script(segments)

        result = generate_narration(script, _voice_map(), output_path=None)

        assert result.output_path.startswith("./data/stories/")
        assert result.output_path.endswith(".mp3")

    @patch("app.services.narration_generator.os.makedirs")
    @patch("app.services.narration_generator.cache_lookup")
    @patch("app.services.narration_generator.mix_narration")
    @patch("app.services.narration_generator.generate_sfx")
    @patch("app.services.narration_generator.generate_audio")
    def test_skips_segments_that_return_none(
        self,
        mock_gen_audio,
        mock_gen_sfx,
        mock_mix,
        mock_cache_lookup,
        mock_makedirs,
    ):
        mock_mix.return_value = MagicMock(spec=AudioSegment)
        mock_cache_lookup.return_value = CacheLookupResult(
            cache_key="abc", cached_path="/cache/abc.mp3", is_hit=False,
        )

        segments = [
            ScriptSegment(type=SegmentType.NARRATION, character="narrator",
                          text="Real text.", tone=None),
            ScriptSegment(type=SegmentType.SFX, description=""),  # empty -> None
            ScriptSegment(type=SegmentType.NARRATION, character="narrator",
                          text="", tone=None),  # empty -> None
        ]
        script = _make_script(segments)

        generate_narration(script, _voice_map(), "/output/story.mp3")

        # Only the first segment should produce a file
        mock_gen_audio.assert_called_once()
        mock_gen_sfx.assert_not_called()
        # mix_narration receives only the one valid segment
        args = mock_mix.call_args.args[0]
        assert len(args) == 1

    @patch("app.services.narration_generator.os.makedirs")
    @patch("app.services.narration_generator.cache_lookup")
    @patch("app.services.narration_generator.mix_narration")
    @patch("app.services.narration_generator.generate_sfx")
    @patch("app.services.narration_generator.generate_audio")
    @patch("app.services.narration_generator.AudioSegment")
    def test_mixed_segment_types(
        self,
        mock_audio_cls,
        mock_gen_audio,
        mock_gen_sfx,
        mock_mix,
        mock_cache_lookup,
        mock_makedirs,
    ):
        """Pipeline with narration, dialogue, sfx, ambient, and pause segments."""
        mock_mix.return_value = MagicMock(spec=AudioSegment)
        mock_silence = MagicMock()
        mock_audio_cls.silent.return_value = mock_silence
        mock_cache_lookup.return_value = CacheLookupResult(
            cache_key="abc", cached_path="/cache/abc.mp3", is_hit=False,
        )

        segments = [
            ScriptSegment(type=SegmentType.NARRATION, character="narrator",
                          text="It began.", tone=None),
            ScriptSegment(type=SegmentType.DIALOGUE, character="sarah",
                          text="What was that?", tone="whisper quietly"),
            ScriptSegment(type=SegmentType.SFX, description="glass shattering"),
            ScriptSegment(type=SegmentType.AMBIENT, description="wind howling", loop=True),
            ScriptSegment(type=SegmentType.PAUSE, duration_ms=3000),
        ]
        script = _make_script(segments)

        result = generate_narration(script, _voice_map(), "/output/full.mp3")
        assert result.output_path == "/output/full.mp3"

        # Voice calls: narration + dialogue = 2
        assert mock_gen_audio.call_count == 2

        # SFX calls: sfx + ambient = 2
        assert mock_gen_sfx.call_count == 2

        # Pause created via AudioSegment.silent
        mock_audio_cls.silent.assert_called_once_with(duration=3000)
        mock_silence.export.assert_called_once()

        # mix_narration receives all 5 segment file tuples
        segment_files = mock_mix.call_args.args[0]
        assert len(segment_files) == 5

    @patch("app.services.narration_generator.os.makedirs")
    @patch("app.services.narration_generator.cache_lookup")
    @patch("app.services.narration_generator.mix_narration")
    def test_empty_script_still_calls_mix(
        self,
        mock_mix,
        mock_cache_lookup,
        mock_makedirs,
    ):
        """A script with no segments should still call mix_narration with an
        empty list and export the result."""
        mock_mix.return_value = MagicMock(spec=AudioSegment)

        script = _make_script([])
        result = generate_narration(script, _voice_map(), "/output/empty.mp3")

        assert result.output_path == "/output/empty.mp3"
        mock_mix.assert_called_once_with([])

    @patch("app.services.narration_generator.os.makedirs")
    @patch("app.services.narration_generator.cache_lookup")
    @patch("app.services.narration_generator.mix_narration")
    @patch("app.services.narration_generator.generate_audio")
    def test_segment_files_paired_with_segment_objects(
        self,
        mock_gen_audio,
        mock_mix,
        mock_cache_lookup,
        mock_makedirs,
    ):
        """mix_narration should receive (path, ScriptSegment) tuples so the
        mixer can inspect segment metadata (type, tone, duration, etc.)."""
        mock_mix.return_value = MagicMock(spec=AudioSegment)
        mock_cache_lookup.return_value = CacheLookupResult(
            cache_key="abc", cached_path="/cache/abc.mp3", is_hit=False,
        )

        seg = ScriptSegment(type=SegmentType.NARRATION, character="narrator",
                            text="Content.", tone="calm")
        script = _make_script([seg])

        generate_narration(script, _voice_map(), "/output/story.mp3")

        segment_files = mock_mix.call_args.args[0]
        assert len(segment_files) == 1
        path, segment_obj = segment_files[0]
        assert path == "/cache/abc.mp3"
        # segment_obj should be the merged version of seg
        assert segment_obj.text == "Content."

    @patch("app.services.narration_generator.os.makedirs")
    @patch("app.services.narration_generator.cache_lookup")
    @patch("app.services.narration_generator.mix_narration")
    @patch("app.services.narration_generator.generate_audio")
    def test_creates_output_directory(
        self,
        mock_gen_audio,
        mock_mix,
        mock_cache_lookup,
        mock_makedirs,
    ):
        mock_mix.return_value = MagicMock(spec=AudioSegment)
        mock_cache_lookup.return_value = CacheLookupResult(
            cache_key="abc", cached_path="/cache/abc.mp3", is_hit=False,
        )

        segments = [
            ScriptSegment(type=SegmentType.NARRATION, character="narrator",
                          text="Hello.", tone=None),
        ]
        script = _make_script(segments)

        generate_narration(script, _voice_map(), "/deep/nested/dir/story.mp3")

        # Should create both the output dir and the segment cache dir
        makedirs_paths = [c.args[0] for c in mock_makedirs.call_args_list]
        assert "/deep/nested/dir" in makedirs_paths


# ---------------------------------------------------------------------------
# Cache integration tests
# ---------------------------------------------------------------------------

class TestCacheIntegration:

    @patch("app.services.narration_generator.os.makedirs")
    @patch("app.services.narration_generator.cache_lookup")
    @patch("app.services.narration_generator.mix_narration")
    @patch("app.services.narration_generator.generate_audio")
    def test_cache_hit_skips_api_call(
        self,
        mock_gen_audio,
        mock_mix,
        mock_cache_lookup,
        mock_makedirs,
    ):
        """When cache returns is_hit=True, the TTS API should NOT be called."""
        mock_mix.return_value = MagicMock(spec=AudioSegment)
        mock_cache_lookup.return_value = CacheLookupResult(
            cache_key="cached123", cached_path="/cache/cached123.mp3", is_hit=True,
        )

        segments = [
            ScriptSegment(type=SegmentType.NARRATION, character="narrator",
                          text="Cached content.", tone="ominous"),
        ]
        script = _make_script(segments)

        result = generate_narration(script, _voice_map(), "/output/story.mp3")

        # API should NOT be called
        mock_gen_audio.assert_not_called()
        # But the cached path should be passed to the mixer
        segment_files = mock_mix.call_args.args[0]
        assert len(segment_files) == 1
        assert segment_files[0][0] == "/cache/cached123.mp3"
        # Cache stats should reflect the hit
        assert result.cache_hits == 1
        assert result.cache_misses == 0

    @patch("app.services.narration_generator.os.makedirs")
    @patch("app.services.narration_generator.cache_lookup")
    @patch("app.services.narration_generator.mix_narration")
    @patch("app.services.narration_generator.generate_audio")
    def test_cache_miss_calls_api_at_cache_path(
        self,
        mock_gen_audio,
        mock_mix,
        mock_cache_lookup,
        mock_makedirs,
    ):
        """On cache miss, the segment should be generated at the cache path."""
        mock_mix.return_value = MagicMock(spec=AudioSegment)
        mock_cache_lookup.return_value = CacheLookupResult(
            cache_key="newkey", cached_path="/cache/newkey.mp3", is_hit=False,
        )

        segments = [
            ScriptSegment(type=SegmentType.NARRATION, character="narrator",
                          text="New content.", tone=None),
        ]
        script = _make_script(segments)

        result = generate_narration(script, _voice_map(), "/output/story.mp3")

        # API should be called with the cache path
        mock_gen_audio.assert_called_once()
        assert mock_gen_audio.call_args.kwargs["output_path"] == "/cache/newkey.mp3"
        assert result.cache_hits == 0
        assert result.cache_misses == 1

    @patch("app.services.narration_generator.os.makedirs")
    @patch("app.services.narration_generator.cache_lookup")
    @patch("app.services.narration_generator.mix_narration")
    @patch("app.services.narration_generator.generate_audio")
    @patch("app.services.narration_generator.generate_sfx")
    def test_mix_receives_both_cached_and_new_segments(
        self,
        mock_gen_sfx,
        mock_gen_audio,
        mock_mix,
        mock_cache_lookup,
        mock_makedirs,
    ):
        """Mixer should receive all segments regardless of cache status."""
        mock_mix.return_value = MagicMock(spec=AudioSegment)

        # First segment is cached, second is not
        mock_cache_lookup.side_effect = [
            CacheLookupResult(cache_key="cached", cached_path="/cache/cached.mp3", is_hit=True),
            CacheLookupResult(cache_key="new", cached_path="/cache/new.mp3", is_hit=False),
        ]

        segments = [
            ScriptSegment(type=SegmentType.NARRATION, character="narrator",
                          text="Cached line.", tone=None),
            ScriptSegment(type=SegmentType.SFX, description="thunder"),
        ]
        script = _make_script(segments)

        result = generate_narration(script, _voice_map(), "/output/story.mp3")

        # Only the SFX should have been generated
        mock_gen_audio.assert_not_called()
        mock_gen_sfx.assert_called_once()

        # Both segments should be passed to the mixer
        segment_files = mock_mix.call_args.args[0]
        assert len(segment_files) == 2
        assert segment_files[0][0] == "/cache/cached.mp3"
        assert segment_files[1][0] == "/cache/new.mp3"

        assert result.cache_hits == 1
        assert result.cache_misses == 1

    @patch("app.services.narration_generator.os.makedirs")
    @patch("app.services.narration_generator.cache_lookup")
    @patch("app.services.narration_generator.mix_narration")
    @patch("app.services.narration_generator.generate_audio")
    def test_bust_cache_forces_regeneration(
        self,
        mock_gen_audio,
        mock_mix,
        mock_cache_lookup,
        mock_makedirs,
    ):
        """When bust_cache=True, even cached segments should be regenerated."""
        mock_mix.return_value = MagicMock(spec=AudioSegment)
        mock_cache_lookup.return_value = CacheLookupResult(
            cache_key="cached", cached_path="/cache/cached.mp3", is_hit=True,
        )

        segments = [
            ScriptSegment(type=SegmentType.NARRATION, character="narrator",
                          text="Will be regenerated.", tone=None),
        ]
        script = _make_script(segments)

        result = generate_narration(
            script, _voice_map(), "/output/story.mp3", bust_cache=True
        )

        # API SHOULD be called despite cache hit
        mock_gen_audio.assert_called_once()
        assert result.cache_hits == 0
        assert result.cache_misses == 1

    @patch("app.services.narration_generator.os.makedirs")
    @patch("app.services.narration_generator.cache_lookup")
    @patch("app.services.narration_generator.mix_narration")
    @patch("app.services.narration_generator.generate_audio")
    def test_result_includes_cache_stats(
        self,
        mock_gen_audio,
        mock_mix,
        mock_cache_lookup,
        mock_makedirs,
    ):
        """NarrationResult should include accurate cache statistics."""
        mock_mix.return_value = MagicMock(spec=AudioSegment)

        # Mix of hits and misses
        mock_cache_lookup.side_effect = [
            CacheLookupResult(cache_key="a", cached_path="/cache/a.mp3", is_hit=True),
            CacheLookupResult(cache_key="b", cached_path="/cache/b.mp3", is_hit=True),
            CacheLookupResult(cache_key="c", cached_path="/cache/c.mp3", is_hit=False),
        ]

        segments = [
            ScriptSegment(type=SegmentType.NARRATION, character="narrator",
                          text="Cached 1.", tone=None),
            ScriptSegment(type=SegmentType.NARRATION, character="sarah",
                          text="Cached 2.", tone=None),
            ScriptSegment(type=SegmentType.NARRATION, character="narrator",
                          text="New.", tone=None),
        ]
        script = _make_script(segments)

        result = generate_narration(script, _voice_map(), "/output/story.mp3")

        assert result.total_segments == 3
        assert result.cache_hits == 2
        assert result.cache_misses == 1


# ---------------------------------------------------------------------------
# _generate_voice_segment  (preset passthrough)
# ---------------------------------------------------------------------------

class TestVoiceSegmentPreset:

    @patch("app.services.narration_generator.generate_audio")
    def test_tone_is_converted_to_preset(self, mock_gen_audio):
        segment = ScriptSegment(
            type=SegmentType.NARRATION,
            character="narrator",
            text="Run!",
            tone="panic and scream",
        )
        _generate_voice_segment(segment, _voice_map(), "/cache/x.mp3")
        assert mock_gen_audio.call_args.kwargs["preset"] == "horror_dialogue"

    @patch("app.services.narration_generator.generate_audio")
    def test_none_tone_gives_horror_narrator_preset(self, mock_gen_audio):
        segment = ScriptSegment(
            type=SegmentType.NARRATION,
            character="narrator",
            text="Something.",
            tone=None,
        )
        _generate_voice_segment(segment, _voice_map(), "/cache/x.mp3")
        assert mock_gen_audio.call_args.kwargs["preset"] == "horror_narrator"


# ---------------------------------------------------------------------------
# _generate_sfx_segment  (duration)
# ---------------------------------------------------------------------------

class TestSfxSegment:

    @patch("app.services.narration_generator.generate_sfx")
    def test_uses_five_second_default_duration(self, mock_gen_sfx):
        segment = ScriptSegment(
            type=SegmentType.SFX,
            description="thunder crack",
        )
        _generate_sfx_segment(segment, "/cache/x.mp3")
        mock_gen_sfx.assert_called_once_with(
            "thunder crack",
            output_path="/cache/x.mp3",
            duration_seconds=5.0,
        )


# ---------------------------------------------------------------------------
# _generate_ambient_segment  (loop flag -> duration)
# ---------------------------------------------------------------------------

class TestAmbientSegment:

    @patch("app.services.narration_generator.generate_sfx")
    def test_no_loop_uses_five_seconds(self, mock_gen_sfx):
        segment = ScriptSegment(
            type=SegmentType.AMBIENT,
            description="crickets",
            loop=False,
        )
        _generate_ambient_segment(segment, "/cache/x.mp3")
        mock_gen_sfx.assert_called_once_with(
            "crickets",
            output_path="/cache/x.mp3",
            duration_seconds=5.0,
        )

    @patch("app.services.narration_generator.generate_sfx")
    def test_loop_uses_ten_seconds(self, mock_gen_sfx):
        segment = ScriptSegment(
            type=SegmentType.AMBIENT,
            description="rain",
            loop=True,
        )
        _generate_ambient_segment(segment, "/cache/x.mp3")
        mock_gen_sfx.assert_called_once_with(
            "rain",
            output_path="/cache/x.mp3",
            duration_seconds=10.0,
        )


# ---------------------------------------------------------------------------
# _generate_pause_segment  (silence creation)
# ---------------------------------------------------------------------------

class TestPauseSegment:

    @patch("app.services.narration_generator.AudioSegment")
    def test_creates_silence_with_given_duration(self, mock_audio_cls):
        mock_silence = MagicMock()
        mock_audio_cls.silent.return_value = mock_silence

        segment = ScriptSegment(type=SegmentType.PAUSE, duration_ms=2500)
        result = _generate_pause_segment(segment, "/cache/pause.mp3")

        assert result == "/cache/pause.mp3"
        mock_audio_cls.silent.assert_called_once_with(duration=2500)
        mock_silence.export.assert_called_once_with(
            "/cache/pause.mp3", format="mp3"
        )

    @patch("app.services.narration_generator.AudioSegment")
    def test_defaults_to_1500ms_when_no_duration(self, mock_audio_cls):
        mock_audio_cls.silent.return_value = MagicMock()

        segment = ScriptSegment(type=SegmentType.PAUSE, duration_ms=None)
        _generate_pause_segment(segment, "/cache/pause.mp3")

        mock_audio_cls.silent.assert_called_once_with(duration=1500)
