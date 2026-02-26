import os
import re
import uuid
import logging
import hashlib
import requests
from typing import List, Optional
from app.config import settings
from app.services.audio_utils import stitch_audio_files, create_tmp_folder, cleanup_temp_files

logger = logging.getLogger(__name__)


class ElevenLabsError(Exception):
    """Raised when an ElevenLabs API call fails."""

    def __init__(self, message: str, status_code: int | None = None, detail: str | None = None):
        self.status_code = status_code
        self.detail = detail
        super().__init__(message)

MAX_TEXT_LENGTH = 4900  # safe margin for ElevenLabs per-request char limit

# Horror-tuned voice presets. Lower stability = more emotional range.
# Higher style = more pronounced character.
VOICE_PRESETS = {
    "horror_narrator": {
        "stability": 0.5,
        "similarity_boost": 0.75,
        "style": 0.45,
    },
    "horror_dialogue": {
        "stability": 0.5,
        "similarity_boost": 0.70,
        "style": 0.50,
    },
    "whisper": {
        "stability": 0.5,
        "similarity_boost": 0.80,
        "style": 0.55,
    },
    "calm": {
        "stability": 0.5,
        "similarity_boost": 0.75,
        "style": 0.30,
    },
}

# ElevenLabs model IDs
MODEL_ELEVEN_V2 = "eleven_multilingual_v2"
MODEL_ELEVEN_V3 = "eleven_v3"

# SFX cache directory
SFX_CACHE_DIR = "./data/sfx_cache"

# Voice preview cache directory
VOICE_PREVIEW_CACHE_DIR = "./data/voice_previews"

# Short dramatic sentence used when generating voice previews
VOICE_PREVIEW_TEXT = "The shadows crept closer, and I knew then that something unspeakable was watching from the darkness."


def generate_audio(
    text: str,
    voice_id: str,
    output_path: Optional[str] = None,
    preset: str = "horror_narrator",
    model_id: str = MODEL_ELEVEN_V3,
) -> str:
    """Generate an audio file for the given text using ElevenLabs TTS.

    Splits the text into sentence-boundary chunks if it exceeds the max chunk
    size, generates each chunk, then stitches them together.
    """
    if not output_path:
        output_path = f"./data/stories/{uuid.uuid4()}.mp3"

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    tmp_folder = create_tmp_folder()
    chunks = chunk_text(text, MAX_TEXT_LENGTH)

    audio_chunks = []
    for idx, chunk in enumerate(chunks):
        tmp_file_name = f"chunk_{uuid.uuid4()}.mp3"
        chunk_output = os.path.join(tmp_folder, tmp_file_name)
        tts_request(chunk, voice_id, chunk_output, preset=preset, model_id=model_id)
        audio_chunks.append(chunk_output)

    if len(audio_chunks) > 1:
        stitch_audio_files(audio_chunks, output_path)
        for f in audio_chunks:
            try:
                os.remove(f)
            except Exception:
                pass
    else:
        os.rename(audio_chunks[0], output_path)

    cleanup_temp_files(tmp_folder, days=3)
    return output_path


def generate_sfx(
    description: str,
    output_path: Optional[str] = None,
    duration_seconds: float = 5.0,
    use_cache: bool = True,
) -> str:
    """Generate a sound effect from a text description using ElevenLabs SFX API.

    Caches generated SFX by description hash so identical descriptions across
    stories don't cost additional API calls.
    """
    os.makedirs(SFX_CACHE_DIR, exist_ok=True)

    # Check cache first
    cache_key = hashlib.sha256(description.lower().strip().encode()).hexdigest()[:16]
    cached_path = os.path.join(SFX_CACHE_DIR, f"{cache_key}.mp3")

    if use_cache and os.path.exists(cached_path):
        logger.info(f"SFX cache hit: '{description[:40]}...'")
        if output_path:
            import shutil
            shutil.copy2(cached_path, output_path)
            return output_path
        return cached_path

    if not output_path:
        output_path = os.path.join(SFX_CACHE_DIR, f"{cache_key}.mp3")

    if not settings.ELEVENLABS_API_KEY:
        raise ElevenLabsError("ELEVENLABS_API_KEY is not set in environment")

    url = "https://api.elevenlabs.io/v1/sound-generation"
    headers = {
        "xi-api-key": settings.ELEVENLABS_API_KEY,
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
    }
    data = {
        "text": description,
        "duration_seconds": duration_seconds,
    }

    logger.info(f"SFX request: description='{description[:50]}...', duration={duration_seconds}s")

    try:
        response = requests.post(url, headers=headers, json=data, stream=True)
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        body = ""
        try:
            body = exc.response.text
        except Exception:
            pass
        status = exc.response.status_code if exc.response is not None else None
        logger.error(f"ElevenLabs SFX failed (HTTP {status}): {body}")
        raise ElevenLabsError(
            f"ElevenLabs SFX API error (HTTP {status}): {body}",
            status_code=status,
            detail=body,
        ) from exc
    except requests.exceptions.ConnectionError as exc:
        logger.error(f"ElevenLabs SFX connection error: {exc}")
        raise ElevenLabsError(f"Could not connect to ElevenLabs API: {exc}") from exc

    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    # Also save to cache if output_path differs
    if output_path != cached_path and use_cache:
        import shutil
        shutil.copy2(output_path, cached_path)

    logger.info(f"SFX generated: '{description[:40]}...' -> {output_path}")
    return output_path


def chunk_text(text: str, max_len: int) -> List[str]:
    """Split text into chunks that respect sentence boundaries.

    Splits on sentence-ending punctuation (.!?) followed by whitespace so that
    ElevenLabs never receives a fragment that starts or ends mid-sentence.
    Falls back to paragraph breaks, then to the hard character limit if a
    single sentence exceeds max_len.
    """
    if len(text) <= max_len:
        return [text]

    sentences = re.split(r"(?<=[.!?])\s+", text)

    chunks = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence

        if len(candidate) <= max_len:
            current = candidate
        else:
            if current:
                chunks.append(current)
            if len(sentence) > max_len:
                paragraphs = sentence.split("\n\n")
                for para in paragraphs:
                    if len(para) <= max_len:
                        chunks.append(para)
                    else:
                        for i in range(0, len(para), max_len):
                            chunks.append(para[i:i + max_len])
                current = ""
            else:
                current = sentence

    if current:
        chunks.append(current)

    return chunks


def tts_request(
    text: str,
    voice_id: str,
    output_file: str,
    preset: str = "horror_narrator",
    model_id: str = MODEL_ELEVEN_V3,
):
    """Call the ElevenLabs TTS API with horror-tuned voice settings."""
    if not settings.ELEVENLABS_API_KEY:
        raise ElevenLabsError("ELEVENLABS_API_KEY is not set in environment")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"

    voice_settings = VOICE_PRESETS.get(preset, VOICE_PRESETS["horror_narrator"])

    headers = {
        "xi-api-key": settings.ELEVENLABS_API_KEY,
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
    }
    data = {
        "text": text,
        "model_id": model_id,
        "voice_settings": voice_settings,
    }

    logger.info(f"TTS request: voice={voice_id}, model={model_id}, preset={preset}, text_len={len(text)}")

    try:
        response = requests.post(url, headers=headers, json=data, stream=True)
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        body = ""
        try:
            body = exc.response.text
        except Exception:
            pass
        status = exc.response.status_code if exc.response is not None else None
        logger.error(f"ElevenLabs TTS failed (HTTP {status}): {body}")
        raise ElevenLabsError(
            f"ElevenLabs TTS API error (HTTP {status}): {body}",
            status_code=status,
            detail=body,
        ) from exc
    except requests.exceptions.ConnectionError as exc:
        logger.error(f"ElevenLabs TTS connection error: {exc}")
        raise ElevenLabsError(f"Could not connect to ElevenLabs API: {exc}") from exc

    with open(output_file, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)


def generate_voice_preview(voice_id: str) -> str:
    """Generate a short horror-themed voice preview sample and cache it.

    Returns the path to the cached MP3 file. If a cached preview already
    exists for this voice_id, returns it immediately without an API call.
    """
    os.makedirs(VOICE_PREVIEW_CACHE_DIR, exist_ok=True)

    cached_path = os.path.join(VOICE_PREVIEW_CACHE_DIR, f"{voice_id}.mp3")

    if os.path.exists(cached_path):
        logger.info(f"Voice preview cache hit: {voice_id}")
        return cached_path

    logger.info(f"Generating voice preview for {voice_id}")
    temp_path = cached_path + f".{uuid.uuid4().hex}.tmp"
    try:
        tts_request(
            text=VOICE_PREVIEW_TEXT,
            voice_id=voice_id,
            output_file=temp_path,
            preset="horror_narrator",
        )
        os.replace(temp_path, cached_path)
    finally:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except OSError:
            logger.debug(f"Failed to remove temporary voice preview file: {temp_path}", exc_info=True)

    return cached_path
