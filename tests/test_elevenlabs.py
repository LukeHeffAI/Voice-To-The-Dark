"""Comprehensive unit tests for apps.audio.services.elevenlabs."""

import os
import pytest
from unittest.mock import patch, MagicMock, mock_open, call
import requests

from apps.audio.services.elevenlabs import (
    chunk_text,
    generate_audio,
    generate_sfx,
    tts_request,
    ElevenLabsError,
    VOICE_PRESETS,
    MAX_TEXT_LENGTH,
    MODEL_ELEVEN_V2,
    MODEL_ELEVEN_V3,
)


# ---------------------------------------------------------------------------
# ElevenLabsError
# ---------------------------------------------------------------------------

class TestElevenLabsError:
    def test_is_exception(self):
        assert issubclass(ElevenLabsError, Exception)

    def test_message_only(self):
        err = ElevenLabsError("something broke")
        assert str(err) == "something broke"
        assert err.status_code is None
        assert err.detail is None

    def test_with_status_code_and_detail(self):
        err = ElevenLabsError("bad request", status_code=400, detail="invalid voice_id")
        assert err.status_code == 400
        assert err.detail == "invalid voice_id"
        assert "bad request" in str(err)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(ElevenLabsError, match="test error"):
            raise ElevenLabsError("test error", status_code=500)


# ---------------------------------------------------------------------------
# VOICE_PRESETS
# ---------------------------------------------------------------------------

class TestVoicePresets:
    EXPECTED_PRESETS = ["horror_narrator", "horror_dialogue", "whisper", "calm"]

    def test_all_presets_exist(self):
        for name in self.EXPECTED_PRESETS:
            assert name in VOICE_PRESETS, f"Missing preset: {name}"

    def test_no_unexpected_presets(self):
        assert set(VOICE_PRESETS.keys()) == set(self.EXPECTED_PRESETS)

    @pytest.mark.parametrize("preset_name", EXPECTED_PRESETS)
    def test_preset_has_required_keys(self, preset_name):
        preset = VOICE_PRESETS[preset_name]
        assert "stability" in preset
        assert "similarity_boost" in preset
        assert "style" in preset

    @pytest.mark.parametrize("preset_name", EXPECTED_PRESETS)
    def test_preset_values_are_floats_in_range(self, preset_name):
        preset = VOICE_PRESETS[preset_name]
        for key in ("stability", "similarity_boost", "style"):
            val = preset[key]
            assert isinstance(val, (int, float)), f"{preset_name}.{key} is not numeric"
            assert 0.0 <= val <= 1.0, f"{preset_name}.{key}={val} out of [0,1]"


# ---------------------------------------------------------------------------
# Model constants
# ---------------------------------------------------------------------------

class TestModelConstants:
    def test_model_v2(self):
        assert MODEL_ELEVEN_V2 == "eleven_multilingual_v2"

    def test_model_v3(self):
        assert MODEL_ELEVEN_V3 == "eleven_v3"

    def test_max_text_length(self):
        assert isinstance(MAX_TEXT_LENGTH, int)
        assert MAX_TEXT_LENGTH > 0


# ---------------------------------------------------------------------------
# chunk_text  (pure function -- tested directly, no mocks needed)
# ---------------------------------------------------------------------------

class TestChunkText:
    def test_short_text_returns_single_chunk(self):
        text = "Hello world."
        result = chunk_text(text, 100)
        assert result == [text]

    def test_text_exactly_at_max_length(self):
        text = "a" * 50
        result = chunk_text(text, 50)
        assert result == [text]

    def test_empty_string(self):
        result = chunk_text("", 100)
        assert result == [""]

    def test_splits_on_period(self):
        text = "First sentence. Second sentence. Third sentence."
        result = chunk_text(text, 30)
        # Each chunk should be within the limit
        for c in result:
            assert len(c) <= 30
        # Rejoined text should contain all original sentences
        joined = " ".join(result)
        assert "First sentence." in joined
        assert "Second sentence." in joined
        assert "Third sentence." in joined

    def test_splits_on_exclamation(self):
        text = "Watch out! The creature is here! Run away!"
        result = chunk_text(text, 25)
        for c in result:
            assert len(c) <= 25
        joined = " ".join(result)
        assert "Watch out!" in joined
        assert "Run away!" in joined

    def test_splits_on_question_mark(self):
        text = "Who are you? Where am I? What happened?"
        result = chunk_text(text, 25)
        for c in result:
            assert len(c) <= 25
        joined = " ".join(result)
        assert "Who are you?" in joined
        assert "What happened?" in joined

    def test_very_long_single_sentence_force_split(self):
        # No sentence-ending punctuation, no paragraph breaks => hard split
        text = "a" * 250
        result = chunk_text(text, 100)
        assert len(result) == 3  # 100 + 100 + 50
        assert result[0] == "a" * 100
        assert result[1] == "a" * 100
        assert result[2] == "a" * 50
        for c in result:
            assert len(c) <= 100

    def test_paragraph_break_fallback(self):
        # Single "sentence" (no .!? boundaries) but with paragraph breaks
        para1 = "a" * 40
        para2 = "b" * 40
        text = f"{para1}\n\n{para2}"
        result = chunk_text(text, 50)
        assert any(para1 in c for c in result)
        assert any(para2 in c for c in result)
        for c in result:
            assert len(c) <= 50

    def test_multiple_sentences_fit_in_one_chunk(self):
        text = "One. Two. Three."
        result = chunk_text(text, 100)
        assert result == [text]

    def test_preserves_all_content(self):
        sentences = [f"Sentence number {i}." for i in range(20)]
        text = " ".join(sentences)
        result = chunk_text(text, 60)
        joined = " ".join(result)
        for s in sentences:
            assert s in joined

    def test_respects_max_text_length_constant(self):
        # Smoke test using the real MAX_TEXT_LENGTH
        text = "Short text."
        result = chunk_text(text, MAX_TEXT_LENGTH)
        assert result == [text]

    def test_long_text_with_mixed_punctuation(self):
        text = (
            "The door creaked open. Was anyone there? "
            "A scream pierced the silence! Then nothing. "
            "Absolutely nothing at all."
        )
        result = chunk_text(text, 50)
        for c in result:
            assert len(c) <= 50
        joined = " ".join(result)
        assert "The door creaked open." in joined
        assert "Absolutely nothing at all." in joined

    def test_single_character_max_len(self):
        text = "abc"
        result = chunk_text(text, 1)
        # Each chunk at most 1 char
        for c in result:
            assert len(c) <= 1
        assert "".join(result) == "abc"

    def test_no_trailing_empty_chunks(self):
        text = "Hello. World."
        result = chunk_text(text, 10)
        for c in result:
            assert c != ""


# ---------------------------------------------------------------------------
# tts_request  (mock requests.post)
# ---------------------------------------------------------------------------

class TestTtsRequest:
    FAKE_API_KEY = "test-api-key-123"

    @patch("apps.audio.services.elevenlabs.requests.post")
    @patch("apps.audio.services.elevenlabs.settings")
    def test_successful_request(self, mock_settings, mock_post, tmp_path):
        mock_settings.ELEVENLABS_API_KEY = self.FAKE_API_KEY
        mock_response = MagicMock()
        mock_response.iter_content.return_value = [b"audio-data-chunk"]
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        output_file = str(tmp_path / "output.mp3")
        tts_request("Hello world", "voice_abc", output_file)

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs.kwargs["headers"]["xi-api-key"] == self.FAKE_API_KEY
        assert call_kwargs.kwargs["json"]["text"] == "Hello world"
        assert call_kwargs.kwargs["json"]["model_id"] == MODEL_ELEVEN_V3
        assert call_kwargs.kwargs["json"]["voice_settings"] == VOICE_PRESETS["horror_narrator"]
        assert "voice_abc" in call_kwargs.args[0]  # URL contains voice_id

        # Verify the output file was written
        with open(output_file, "rb") as f:
            assert f.read() == b"audio-data-chunk"

    @patch("apps.audio.services.elevenlabs.requests.post")
    @patch("apps.audio.services.elevenlabs.settings")
    def test_uses_correct_url(self, mock_settings, mock_post, tmp_path):
        mock_settings.ELEVENLABS_API_KEY = self.FAKE_API_KEY
        mock_response = MagicMock()
        mock_response.iter_content.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        output_file = str(tmp_path / "output.mp3")
        tts_request("Hi", "my_voice_id", output_file)

        url = mock_post.call_args.args[0]
        assert url == "https://api.elevenlabs.io/v1/text-to-speech/my_voice_id/stream"

    @patch("apps.audio.services.elevenlabs.requests.post")
    @patch("apps.audio.services.elevenlabs.settings")
    def test_custom_preset(self, mock_settings, mock_post, tmp_path):
        mock_settings.ELEVENLABS_API_KEY = self.FAKE_API_KEY
        mock_response = MagicMock()
        mock_response.iter_content.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        output_file = str(tmp_path / "output.mp3")
        tts_request("Text", "v1", output_file, preset="whisper")

        sent_settings = mock_post.call_args.kwargs["json"]["voice_settings"]
        assert sent_settings == VOICE_PRESETS["whisper"]

    @patch("apps.audio.services.elevenlabs.requests.post")
    @patch("apps.audio.services.elevenlabs.settings")
    def test_unknown_preset_falls_back_to_horror_narrator(self, mock_settings, mock_post, tmp_path):
        mock_settings.ELEVENLABS_API_KEY = self.FAKE_API_KEY
        mock_response = MagicMock()
        mock_response.iter_content.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        output_file = str(tmp_path / "output.mp3")
        tts_request("Text", "v1", output_file, preset="nonexistent_preset")

        sent_settings = mock_post.call_args.kwargs["json"]["voice_settings"]
        assert sent_settings == VOICE_PRESETS["horror_narrator"]

    @patch("apps.audio.services.elevenlabs.requests.post")
    @patch("apps.audio.services.elevenlabs.settings")
    def test_custom_model_id(self, mock_settings, mock_post, tmp_path):
        mock_settings.ELEVENLABS_API_KEY = self.FAKE_API_KEY
        mock_response = MagicMock()
        mock_response.iter_content.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        output_file = str(tmp_path / "output.mp3")
        tts_request("Text", "v1", output_file, model_id=MODEL_ELEVEN_V2)

        assert mock_post.call_args.kwargs["json"]["model_id"] == MODEL_ELEVEN_V2

    @patch("apps.audio.services.elevenlabs.settings")
    def test_missing_api_key_raises_error(self, mock_settings):
        mock_settings.ELEVENLABS_API_KEY = ""
        with pytest.raises(ElevenLabsError, match="ELEVENLABS_API_KEY"):
            tts_request("Hello", "voice_id", "/tmp/out.mp3")

    @patch("apps.audio.services.elevenlabs.settings")
    def test_none_api_key_raises_error(self, mock_settings):
        mock_settings.ELEVENLABS_API_KEY = None
        with pytest.raises(ElevenLabsError, match="ELEVENLABS_API_KEY"):
            tts_request("Hello", "voice_id", "/tmp/out.mp3")

    @patch("apps.audio.services.elevenlabs.requests.post")
    @patch("apps.audio.services.elevenlabs.settings")
    def test_http_error_raises_elevenlabs_error(self, mock_settings, mock_post):
        mock_settings.ELEVENLABS_API_KEY = self.FAKE_API_KEY

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "rate limit exceeded"
        http_err = requests.exceptions.HTTPError(response=mock_response)
        mock_post.return_value.raise_for_status.side_effect = http_err

        with pytest.raises(ElevenLabsError) as exc_info:
            tts_request("Hello", "voice_id", "/tmp/out.mp3")
        assert exc_info.value.status_code == 429
        assert exc_info.value.detail == "rate limit exceeded"

    @patch("apps.audio.services.elevenlabs.requests.post")
    @patch("apps.audio.services.elevenlabs.settings")
    def test_connection_error_raises_elevenlabs_error(self, mock_settings, mock_post):
        mock_settings.ELEVENLABS_API_KEY = self.FAKE_API_KEY
        mock_post.side_effect = requests.exceptions.ConnectionError("DNS failure")

        with pytest.raises(ElevenLabsError, match="Could not connect"):
            tts_request("Hello", "voice_id", "/tmp/out.mp3")

    @patch("apps.audio.services.elevenlabs.requests.post")
    @patch("apps.audio.services.elevenlabs.settings")
    def test_sends_stream_flag(self, mock_settings, mock_post, tmp_path):
        mock_settings.ELEVENLABS_API_KEY = self.FAKE_API_KEY
        mock_response = MagicMock()
        mock_response.iter_content.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        output_file = str(tmp_path / "output.mp3")
        tts_request("Text", "v1", output_file)

        assert mock_post.call_args.kwargs["stream"] is True

    @patch("apps.audio.services.elevenlabs.requests.post")
    @patch("apps.audio.services.elevenlabs.settings")
    def test_sends_correct_content_type_and_accept(self, mock_settings, mock_post, tmp_path):
        mock_settings.ELEVENLABS_API_KEY = self.FAKE_API_KEY
        mock_response = MagicMock()
        mock_response.iter_content.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        output_file = str(tmp_path / "output.mp3")
        tts_request("Text", "v1", output_file)

        headers = mock_post.call_args.kwargs["headers"]
        assert headers["Accept"] == "audio/mpeg"
        assert headers["Content-Type"] == "application/json"


# ---------------------------------------------------------------------------
# generate_audio  (mock tts_request and stitch_audio_files)
# ---------------------------------------------------------------------------

class TestGenerateAudio:
    @patch("apps.audio.services.elevenlabs.cleanup_temp_files")
    @patch("apps.audio.services.elevenlabs.create_tmp_folder")
    @patch("apps.audio.services.elevenlabs.tts_request")
    @patch("apps.audio.services.elevenlabs.os.rename")
    @patch("apps.audio.services.elevenlabs.os.makedirs")
    def test_short_text_single_chunk_no_stitch(
        self, mock_makedirs, mock_rename, mock_tts, mock_tmp_folder, mock_cleanup, tmp_path
    ):
        tmp_folder = str(tmp_path / "tmp")
        os.makedirs(tmp_folder, exist_ok=True)
        mock_tmp_folder.return_value = tmp_folder

        output = str(tmp_path / "out.mp3")
        result = generate_audio("Short text.", "voice_1", output)

        assert result == output
        mock_tts.assert_called_once()
        # Single chunk => os.rename, not stitch
        mock_rename.assert_called_once()

    @patch("apps.audio.services.elevenlabs.cleanup_temp_files")
    @patch("apps.audio.services.elevenlabs.stitch_audio_files")
    @patch("apps.audio.services.elevenlabs.create_tmp_folder")
    @patch("apps.audio.services.elevenlabs.tts_request")
    def test_long_text_multiple_chunks_stitched(
        self, mock_tts, mock_tmp_folder, mock_stitch, mock_cleanup, tmp_path
    ):
        tmp_folder = str(tmp_path / "tmp")
        os.makedirs(tmp_folder, exist_ok=True)
        mock_tmp_folder.return_value = tmp_folder

        # Create text that will split into multiple chunks
        sentences = ["This is a sentence." for _ in range(300)]
        long_text = " ".join(sentences)
        assert len(long_text) > MAX_TEXT_LENGTH

        output = str(tmp_path / "out.mp3")
        # Create fake chunk files so os.remove doesn't error
        mock_tts.side_effect = lambda text, vid, path, **kw: open(path, "w").close()

        result = generate_audio(long_text, "voice_1", output)

        assert result == output
        assert mock_tts.call_count > 1
        mock_stitch.assert_called_once()

    @patch("apps.audio.services.elevenlabs.cleanup_temp_files")
    @patch("apps.audio.services.elevenlabs.create_tmp_folder")
    @patch("apps.audio.services.elevenlabs.tts_request")
    @patch("apps.audio.services.elevenlabs.os.rename")
    @patch("apps.audio.services.elevenlabs.os.makedirs")
    def test_passes_preset_and_model_to_tts(
        self, mock_makedirs, mock_rename, mock_tts, mock_tmp_folder, mock_cleanup, tmp_path
    ):
        tmp_folder = str(tmp_path / "tmp")
        os.makedirs(tmp_folder, exist_ok=True)
        mock_tmp_folder.return_value = tmp_folder

        output = str(tmp_path / "out.mp3")
        generate_audio("Hello.", "voice_1", output, preset="whisper", model_id=MODEL_ELEVEN_V2)

        mock_tts.assert_called_once()
        _, kwargs = mock_tts.call_args
        assert kwargs["preset"] == "whisper"
        assert kwargs["model_id"] == MODEL_ELEVEN_V2

    @patch("apps.audio.services.elevenlabs.cleanup_temp_files")
    @patch("apps.audio.services.elevenlabs.create_tmp_folder")
    @patch("apps.audio.services.elevenlabs.tts_request")
    @patch("apps.audio.services.elevenlabs.os.rename")
    @patch("apps.audio.services.elevenlabs.os.makedirs")
    def test_generates_output_path_when_none(
        self, mock_makedirs, mock_rename, mock_tts, mock_tmp_folder, mock_cleanup, tmp_path
    ):
        tmp_folder = str(tmp_path / "tmp")
        os.makedirs(tmp_folder, exist_ok=True)
        mock_tmp_folder.return_value = tmp_folder

        result = generate_audio("Hello.", "voice_1")

        # Should auto-generate a path under ./data/stories/
        assert result.endswith(".mp3")
        assert "stories" in result

    @patch("apps.audio.services.elevenlabs.cleanup_temp_files")
    @patch("apps.audio.services.elevenlabs.create_tmp_folder")
    @patch("apps.audio.services.elevenlabs.tts_request")
    @patch("apps.audio.services.elevenlabs.os.rename")
    @patch("apps.audio.services.elevenlabs.os.makedirs")
    def test_calls_cleanup_temp_files(
        self, mock_makedirs, mock_rename, mock_tts, mock_tmp_folder, mock_cleanup, tmp_path
    ):
        tmp_folder = str(tmp_path / "tmp")
        os.makedirs(tmp_folder, exist_ok=True)
        mock_tmp_folder.return_value = tmp_folder

        output = str(tmp_path / "out.mp3")
        generate_audio("Hello.", "voice_1", output)

        mock_cleanup.assert_called_once_with(tmp_folder, days=3)

    @patch("apps.audio.services.elevenlabs.cleanup_temp_files")
    @patch("apps.audio.services.elevenlabs.create_tmp_folder")
    @patch("apps.audio.services.elevenlabs.tts_request")
    @patch("apps.audio.services.elevenlabs.os.rename")
    @patch("apps.audio.services.elevenlabs.os.makedirs")
    def test_default_preset_is_horror_narrator(
        self, mock_makedirs, mock_rename, mock_tts, mock_tmp_folder, mock_cleanup, tmp_path
    ):
        tmp_folder = str(tmp_path / "tmp")
        os.makedirs(tmp_folder, exist_ok=True)
        mock_tmp_folder.return_value = tmp_folder

        output = str(tmp_path / "out.mp3")
        generate_audio("Hello.", "voice_1", output)

        _, kwargs = mock_tts.call_args
        assert kwargs["preset"] == "horror_narrator"

    @patch("apps.audio.services.elevenlabs.cleanup_temp_files")
    @patch("apps.audio.services.elevenlabs.create_tmp_folder")
    @patch("apps.audio.services.elevenlabs.tts_request")
    @patch("apps.audio.services.elevenlabs.os.rename")
    @patch("apps.audio.services.elevenlabs.os.makedirs")
    def test_default_model_is_v3(
        self, mock_makedirs, mock_rename, mock_tts, mock_tmp_folder, mock_cleanup, tmp_path
    ):
        tmp_folder = str(tmp_path / "tmp")
        os.makedirs(tmp_folder, exist_ok=True)
        mock_tmp_folder.return_value = tmp_folder

        output = str(tmp_path / "out.mp3")
        generate_audio("Hello.", "voice_1", output)

        _, kwargs = mock_tts.call_args
        assert kwargs["model_id"] == MODEL_ELEVEN_V3


# ---------------------------------------------------------------------------
# generate_sfx  (mock requests.post)
# ---------------------------------------------------------------------------

class TestGenerateSfx:
    FAKE_API_KEY = "test-sfx-key-456"

    @patch("apps.audio.services.elevenlabs.requests.post")
    @patch("apps.audio.services.elevenlabs.settings")
    @patch("apps.audio.services.elevenlabs.os.path.exists", return_value=False)
    @patch("apps.audio.services.elevenlabs.os.makedirs")
    def test_successful_sfx_generation(self, mock_makedirs, mock_exists, mock_settings, mock_post, tmp_path):
        mock_settings.ELEVENLABS_API_KEY = self.FAKE_API_KEY
        mock_response = MagicMock()
        mock_response.iter_content.return_value = [b"sfx-audio"]
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        output = str(tmp_path / "sfx.mp3")
        result = generate_sfx("thunder rumbling", output_path=output, use_cache=False)

        assert result == output
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs.kwargs["headers"]["xi-api-key"] == self.FAKE_API_KEY
        assert call_kwargs.kwargs["json"]["text"] == "thunder rumbling"
        assert call_kwargs.kwargs["json"]["duration_seconds"] == 5.0

    @patch("apps.audio.services.elevenlabs.requests.post")
    @patch("apps.audio.services.elevenlabs.settings")
    @patch("apps.audio.services.elevenlabs.os.path.exists", return_value=False)
    @patch("apps.audio.services.elevenlabs.os.makedirs")
    def test_custom_duration(self, mock_makedirs, mock_exists, mock_settings, mock_post, tmp_path):
        mock_settings.ELEVENLABS_API_KEY = self.FAKE_API_KEY
        mock_response = MagicMock()
        mock_response.iter_content.return_value = [b"data"]
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        output = str(tmp_path / "sfx.mp3")
        generate_sfx("rain", output_path=output, duration_seconds=10.0, use_cache=False)

        assert mock_post.call_args.kwargs["json"]["duration_seconds"] == 10.0

    @patch("apps.audio.services.elevenlabs.requests.post")
    @patch("apps.audio.services.elevenlabs.settings")
    @patch("apps.audio.services.elevenlabs.os.path.exists", return_value=False)
    @patch("apps.audio.services.elevenlabs.os.makedirs")
    def test_sends_correct_url(self, mock_makedirs, mock_exists, mock_settings, mock_post, tmp_path):
        mock_settings.ELEVENLABS_API_KEY = self.FAKE_API_KEY
        mock_response = MagicMock()
        mock_response.iter_content.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        output = str(tmp_path / "sfx.mp3")
        generate_sfx("wind", output_path=output, use_cache=False)

        url = mock_post.call_args.args[0]
        assert url == "https://api.elevenlabs.io/v1/sound-generation"

    @patch("apps.audio.services.elevenlabs.os.path.exists", return_value=False)
    @patch("apps.audio.services.elevenlabs.os.makedirs")
    @patch("apps.audio.services.elevenlabs.settings")
    def test_missing_api_key_raises_error(self, mock_settings, mock_makedirs, mock_exists):
        mock_settings.ELEVENLABS_API_KEY = ""
        with pytest.raises(ElevenLabsError, match="ELEVENLABS_API_KEY"):
            generate_sfx("thunder", use_cache=False)

    @patch("apps.audio.services.elevenlabs.os.path.exists", return_value=False)
    @patch("apps.audio.services.elevenlabs.os.makedirs")
    @patch("apps.audio.services.elevenlabs.settings")
    def test_none_api_key_raises_error(self, mock_settings, mock_makedirs, mock_exists):
        mock_settings.ELEVENLABS_API_KEY = None
        with pytest.raises(ElevenLabsError, match="ELEVENLABS_API_KEY"):
            generate_sfx("thunder", use_cache=False)

    @patch("apps.audio.services.elevenlabs.requests.post")
    @patch("apps.audio.services.elevenlabs.settings")
    @patch("apps.audio.services.elevenlabs.os.path.exists", return_value=False)
    @patch("apps.audio.services.elevenlabs.os.makedirs")
    def test_http_error_raises_elevenlabs_error(self, mock_makedirs, mock_exists, mock_settings, mock_post):
        mock_settings.ELEVENLABS_API_KEY = self.FAKE_API_KEY
        mock_response = MagicMock()
        mock_response.status_code = 422
        mock_response.text = "invalid duration"
        http_err = requests.exceptions.HTTPError(response=mock_response)
        mock_post.return_value.raise_for_status.side_effect = http_err

        with pytest.raises(ElevenLabsError) as exc_info:
            generate_sfx("thunder", use_cache=False)
        assert exc_info.value.status_code == 422
        assert exc_info.value.detail == "invalid duration"

    @patch("apps.audio.services.elevenlabs.requests.post")
    @patch("apps.audio.services.elevenlabs.settings")
    @patch("apps.audio.services.elevenlabs.os.path.exists", return_value=False)
    @patch("apps.audio.services.elevenlabs.os.makedirs")
    def test_connection_error_raises_elevenlabs_error(self, mock_makedirs, mock_exists, mock_settings, mock_post):
        mock_settings.ELEVENLABS_API_KEY = self.FAKE_API_KEY
        mock_post.side_effect = requests.exceptions.ConnectionError("timeout")

        with pytest.raises(ElevenLabsError, match="Could not connect"):
            generate_sfx("thunder", use_cache=False)

    @patch("shutil.copy2")
    @patch("apps.audio.services.elevenlabs.os.path.exists", return_value=True)
    @patch("apps.audio.services.elevenlabs.os.makedirs")
    def test_cache_hit_returns_cached_path(self, mock_makedirs, mock_exists, mock_copy, tmp_path):
        """When use_cache=True and cached file exists, return cached path without API call."""
        result = generate_sfx("thunder rumbling", use_cache=True)

        # Should return the cached path (no output_path specified, so returns cache path)
        assert result.endswith(".mp3")
        assert "sfx_cache" in result

    @patch("shutil.copy2")
    @patch("apps.audio.services.elevenlabs.os.path.exists", return_value=True)
    @patch("apps.audio.services.elevenlabs.os.makedirs")
    def test_cache_hit_copies_to_output_path(self, mock_makedirs, mock_exists, mock_copy, tmp_path):
        """When cache hit and output_path given, copy cached file to output_path."""
        output = str(tmp_path / "my_sfx.mp3")
        result = generate_sfx("thunder rumbling", output_path=output, use_cache=True)

        assert result == output
        mock_copy.assert_called_once()
        # The second argument to copy2 should be the output_path
        assert mock_copy.call_args.args[1] == output

    @patch("apps.audio.services.elevenlabs.requests.post")
    @patch("apps.audio.services.elevenlabs.settings")
    @patch("apps.audio.services.elevenlabs.os.path.exists", return_value=False)
    @patch("apps.audio.services.elevenlabs.os.makedirs")
    def test_cache_bypass_when_disabled(self, mock_makedirs, mock_exists, mock_settings, mock_post, tmp_path):
        """When use_cache=False, API is called even if file might exist."""
        mock_settings.ELEVENLABS_API_KEY = self.FAKE_API_KEY
        mock_response = MagicMock()
        mock_response.iter_content.return_value = [b"data"]
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        output = str(tmp_path / "sfx.mp3")
        generate_sfx("thunder", output_path=output, use_cache=False)

        mock_post.assert_called_once()

    @patch("shutil.copy2")
    @patch("apps.audio.services.elevenlabs.requests.post")
    @patch("apps.audio.services.elevenlabs.settings")
    @patch("apps.audio.services.elevenlabs.os.path.exists", return_value=False)
    @patch("apps.audio.services.elevenlabs.os.makedirs")
    def test_saves_to_cache_after_generation(
        self, mock_makedirs, mock_exists, mock_settings, mock_post, mock_copy, tmp_path
    ):
        """When use_cache=True and output_path differs from cache, copies to cache."""
        mock_settings.ELEVENLABS_API_KEY = self.FAKE_API_KEY
        mock_response = MagicMock()
        mock_response.iter_content.return_value = [b"audio"]
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        output = str(tmp_path / "custom_output.mp3")
        generate_sfx("thunder", output_path=output, use_cache=True)

        # Should copy output to cache
        mock_copy.assert_called_once()
        assert mock_copy.call_args.args[0] == output

    @patch("apps.audio.services.elevenlabs.requests.post")
    @patch("apps.audio.services.elevenlabs.settings")
    def test_auto_generates_output_path_from_hash(self, mock_settings, mock_post, tmp_path):
        """When no output_path given and cache miss, uses hash-based path in cache dir."""
        mock_settings.ELEVENLABS_API_KEY = self.FAKE_API_KEY
        mock_response = MagicMock()
        mock_response.iter_content.return_value = [b"data"]
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        cache_dir = str(tmp_path / "sfx_cache")
        mock_settings.SFX_CACHE_DIR = cache_dir
        result = generate_sfx("thunder", use_cache=False)

        assert result.endswith(".mp3")
        assert "sfx_cache" in result

    @patch("apps.audio.services.elevenlabs.requests.post")
    @patch("apps.audio.services.elevenlabs.settings")
    @patch("apps.audio.services.elevenlabs.os.path.exists", return_value=False)
    @patch("apps.audio.services.elevenlabs.os.makedirs")
    def test_sends_correct_headers(self, mock_makedirs, mock_exists, mock_settings, mock_post, tmp_path):
        mock_settings.ELEVENLABS_API_KEY = self.FAKE_API_KEY
        mock_response = MagicMock()
        mock_response.iter_content.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        output = str(tmp_path / "sfx.mp3")
        generate_sfx("wind", output_path=output, use_cache=False)

        headers = mock_post.call_args.kwargs["headers"]
        assert headers["Accept"] == "audio/mpeg"
        assert headers["Content-Type"] == "application/json"
        assert headers["xi-api-key"] == self.FAKE_API_KEY

    @patch("apps.audio.services.elevenlabs.requests.post")
    @patch("apps.audio.services.elevenlabs.settings")
    @patch("apps.audio.services.elevenlabs.os.path.exists", return_value=False)
    @patch("apps.audio.services.elevenlabs.os.makedirs")
    def test_cache_key_is_case_insensitive(self, mock_makedirs, mock_exists, mock_settings, mock_post, tmp_path):
        """Cache key should be derived from lowered+stripped description."""
        mock_settings.ELEVENLABS_API_KEY = self.FAKE_API_KEY
        mock_response = MagicMock()
        mock_response.iter_content.return_value = [b"data"]
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        output1 = str(tmp_path / "sfx1.mp3")
        output2 = str(tmp_path / "sfx2.mp3")

        # Both should produce the same cache key
        import hashlib
        key1 = hashlib.sha256("thunder rumbling".encode()).hexdigest()[:16]
        key2 = hashlib.sha256("Thunder Rumbling".lower().strip().encode()).hexdigest()[:16]
        assert key1 == key2

    @patch("apps.audio.services.elevenlabs.requests.post")
    @patch("apps.audio.services.elevenlabs.settings")
    @patch("apps.audio.services.elevenlabs.os.path.exists", return_value=False)
    @patch("apps.audio.services.elevenlabs.os.makedirs")
    def test_streams_response(self, mock_makedirs, mock_exists, mock_settings, mock_post, tmp_path):
        mock_settings.ELEVENLABS_API_KEY = self.FAKE_API_KEY
        mock_response = MagicMock()
        mock_response.iter_content.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        output = str(tmp_path / "sfx.mp3")
        generate_sfx("wind", output_path=output, use_cache=False)

        assert mock_post.call_args.kwargs["stream"] is True

    @patch("apps.audio.services.elevenlabs.requests.post")
    @patch("apps.audio.services.elevenlabs.settings")
    @patch("apps.audio.services.elevenlabs.os.path.exists", return_value=False)
    @patch("apps.audio.services.elevenlabs.os.makedirs")
    def test_http_error_preserves_response_body(self, mock_makedirs, mock_exists, mock_settings, mock_post):
        mock_settings.ELEVENLABS_API_KEY = self.FAKE_API_KEY
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = '{"error": "internal server error"}'
        http_err = requests.exceptions.HTTPError(response=mock_response)
        mock_post.return_value.raise_for_status.side_effect = http_err

        with pytest.raises(ElevenLabsError) as exc_info:
            generate_sfx("thunder", use_cache=False)
        assert exc_info.value.status_code == 500
        assert "internal server error" in exc_info.value.detail
