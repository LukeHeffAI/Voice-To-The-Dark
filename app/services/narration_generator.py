import os
import uuid
import logging
from pydub import AudioSegment

from app.schemas.narration import NarrationScript, SegmentType, ScriptSegment
from app.services.elevenlabs import generate_audio, generate_sfx
from app.services.audio_mixer import mix_narration
from app.services.audio_utils import create_tmp_folder

logger = logging.getLogger(__name__)

DEFAULT_NARRATOR_VOICE = "pNInz6obpgDQGcFmaJgB"  # ElevenLabs "Adam"


def generate_narration(
    script: NarrationScript,
    voice_map: dict[str, str],
    output_path: str | None = None,
) -> str:
    """Walk through a narration script, generate all audio segments, then mix
    them into a fully produced audio file.

    This function handles generation (calling TTS and SFX APIs). The actual
    mixing — layering ambient, placing SFX, crossfades, fades, normalization —
    is delegated to audio_mixer.mix_narration().

    Args:
        script: The structured narration script from the script adapter.
        voice_map: Maps character keys (e.g. "narrator", "sarah") to
                   ElevenLabs voice IDs.
        output_path: Where to write the final mixed audio. Auto-generated if None.

    Returns:
        Path to the final audio file.
    """
    if not output_path:
        output_path = f"./data/stories/{uuid.uuid4()}.mp3"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    tmp_folder = create_tmp_folder()

    # --- Generate all segments ---
    segment_files: list[tuple[str, ScriptSegment]] = []

    for i, segment in enumerate(script.segments):
        logger.info(f"Generating segment {i + 1}/{len(script.segments)}: {segment.type}")

        path = _generate_segment(segment, voice_map, tmp_folder, i)
        if path:
            segment_files.append((path, segment))

    # --- Mix everything via the dedicated mixer ---
    final = mix_narration(segment_files)
    final.export(output_path, format="mp3")

    # --- Clean up temp files ---
    for path, _ in segment_files:
        try:
            os.remove(path)
        except Exception:
            pass

    logger.info(f"Narration complete: {output_path} ({len(segment_files)} segments)")
    return output_path


def _generate_segment(
    segment: ScriptSegment,
    voice_map: dict[str, str],
    tmp_folder: str,
    index: int,
) -> str | None:
    """Generate a single audio segment based on its type."""

    if segment.type in (SegmentType.NARRATION, SegmentType.DIALOGUE):
        return _generate_voice_segment(segment, voice_map, tmp_folder, index)
    elif segment.type == SegmentType.SFX:
        return _generate_sfx_segment(segment, tmp_folder, index)
    elif segment.type == SegmentType.AMBIENT:
        return _generate_ambient_segment(segment, tmp_folder, index)
    elif segment.type == SegmentType.PAUSE:
        return _generate_pause_segment(segment, tmp_folder, index)
    return None


def _generate_voice_segment(
    segment: ScriptSegment,
    voice_map: dict[str, str],
    tmp_folder: str,
    index: int,
) -> str | None:
    """Generate a voice segment (narration or dialogue)."""
    if not segment.text:
        return None

    character = segment.character or "narrator"
    voice_id = voice_map.get(character, voice_map.get("narrator", DEFAULT_NARRATOR_VOICE))
    preset = _tone_to_preset(segment.tone)

    out_path = os.path.join(tmp_folder, f"seg_{index:04d}_voice.mp3")
    generate_audio(segment.text, voice_id, output_path=out_path, preset=preset)
    return out_path


def _generate_sfx_segment(
    segment: ScriptSegment,
    tmp_folder: str,
    index: int,
) -> str | None:
    """Generate a sound effect segment."""
    if not segment.description:
        return None

    out_path = os.path.join(tmp_folder, f"seg_{index:04d}_sfx.mp3")
    generate_sfx(segment.description, output_path=out_path, duration_seconds=5.0)
    return out_path


def _generate_ambient_segment(
    segment: ScriptSegment,
    tmp_folder: str,
    index: int,
) -> str | None:
    """Generate an ambient sound segment."""
    if not segment.description:
        return None

    duration = 10.0 if segment.loop else 5.0
    out_path = os.path.join(tmp_folder, f"seg_{index:04d}_ambient.mp3")
    generate_sfx(segment.description, output_path=out_path, duration_seconds=duration)
    return out_path


def _generate_pause_segment(
    segment: ScriptSegment,
    tmp_folder: str,
    index: int,
) -> str | None:
    """Generate a silence segment of the specified duration."""
    duration_ms = segment.duration_ms or 1500
    silence = AudioSegment.silent(duration=duration_ms)
    out_path = os.path.join(tmp_folder, f"seg_{index:04d}_pause.mp3")
    silence.export(out_path, format="mp3")
    return out_path


def _tone_to_preset(tone: str | None) -> str:
    """Map a tone description from the script to an ElevenLabs voice preset."""
    if not tone:
        return "horror_narrator"

    tone_lower = tone.lower()
    if any(word in tone_lower for word in ["whisper", "quiet", "hushed", "soft"]):
        return "whisper"
    if any(word in tone_lower for word in ["calm", "steady", "composed", "matter-of-fact"]):
        return "calm"
    if any(word in tone_lower for word in ["panic", "scream", "shout", "frantic", "desperate", "terrified"]):
        return "horror_dialogue"
    return "horror_narrator"
