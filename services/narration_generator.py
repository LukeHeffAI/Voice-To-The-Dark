import os
import uuid
import logging
from dataclasses import dataclass
from pydub import AudioSegment

from django.conf import settings
from schemas.narration import NarrationScript, SegmentType, ScriptSegment
from services.elevenlabs import generate_audio, generate_sfx
from services.audio_mixer import mix_narration
from services.segment_cache import lookup as cache_lookup, SEGMENT_CACHE_DIR

logger = logging.getLogger(__name__)

DEFAULT_NARRATOR_VOICE = "pNInz6obpgDQGcFmaJgB"  # ElevenLabs "Adam"


@dataclass
class NarrationResult:
    """Result from generate_narration including cache statistics."""

    output_path: str
    cache_hits: int
    cache_misses: int
    total_segments: int


def generate_narration(
    script: NarrationScript,
    voice_map: dict[str, str],
    output_path: str | None = None,
    bust_cache: bool = False,
    progress_callback=None,
) -> NarrationResult:
    """Walk through a narration script, generate all audio segments, then mix
    them into a fully produced audio file.

    Uses a persistent segment cache to skip TTS/SFX API calls for segments
    whose content hasn't changed since the last generation. The mixing step
    always runs in full to ensure correct timing and flow.

    Args:
        script: The structured narration script from the script adapter.
        voice_map: Maps character keys (e.g. "narrator", "sarah") to
                   ElevenLabs voice IDs.
        output_path: Where to write the final mixed audio. Auto-generated if None.
        bust_cache: If True, ignore the segment cache and regenerate everything.
        progress_callback: Optional callable(current, total, message) for progress
                          reporting. Called after each segment is processed.

    Returns:
        NarrationResult with the output path and cache statistics.
    """
    if not output_path:
        output_path = os.path.join(str(settings.STORIES_DIR), f"{uuid.uuid4()}.mp3")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    os.makedirs(SEGMENT_CACHE_DIR, exist_ok=True)

    # --- Merge consecutive same-character voice segments ---
    merged_segments = _group_consecutive_segments(script.segments)
    logger.info(
        f"Segment grouping: {len(script.segments)} original -> "
        f"{len(merged_segments)} after merging consecutive lines"
    )

    # --- Generate all segments (with caching) ---
    segment_files: list[tuple[str, ScriptSegment]] = []
    cache_hits = 0
    cache_misses = 0

    for i, segment in enumerate(merged_segments):
        # Resolve voice_id and preset for cache key computation
        voice_id = None
        preset = None
        if segment.type in (SegmentType.NARRATION, SegmentType.DIALOGUE):
            character = segment.character or "narrator"
            voice_id = voice_map.get(
                character, voice_map.get("narrator", DEFAULT_NARRATOR_VOICE)
            )
            preset = _tone_to_preset(segment.tone)

        # Check cache (unless bust_cache is set)
        cache_result = cache_lookup(segment, voice_id=voice_id, preset=preset)

        if cache_result.is_hit and not bust_cache:
            cache_hits += 1
            logger.info(
                f"Reusing cached segment {i + 1}/{len(merged_segments)}: "
                f"{segment.type.value}"
            )
            segment_files.append((cache_result.cached_path, segment))
        else:
            cache_misses += 1
            logger.info(
                f"Generating segment {i + 1}/{len(merged_segments)}: "
                f"{segment.type.value}"
            )
            path = _generate_segment(
                segment, voice_map, cache_result.cached_path
            )
            if path:
                segment_files.append((path, segment))

        if progress_callback:
            progress_callback(
                i + 1,
                len(merged_segments),
                f"{'Cached' if (cache_result.is_hit and not bust_cache) else 'Generated'} "
                f"segment {i + 1}/{len(merged_segments)}: {segment.type.value}",
            )

    # --- Mix everything via the dedicated mixer ---
    final = mix_narration(segment_files)
    final.export(output_path, format="mp3")

    logger.info(
        f"Narration complete: {output_path} ({len(segment_files)} segments, "
        f"{cache_hits} cached, {cache_misses} generated)"
    )
    return NarrationResult(
        output_path=output_path,
        cache_hits=cache_hits,
        cache_misses=cache_misses,
        total_segments=len(merged_segments),
    )


def _generate_segment(
    segment: ScriptSegment,
    voice_map: dict[str, str],
    output_path: str,
) -> str | None:
    """Generate a single audio segment based on its type.

    The output_path is the cache location where the file will be written
    so it can be reused on subsequent generations.
    """
    if segment.type in (SegmentType.NARRATION, SegmentType.DIALOGUE):
        return _generate_voice_segment(segment, voice_map, output_path)
    elif segment.type == SegmentType.SFX:
        return _generate_sfx_segment(segment, output_path)
    elif segment.type == SegmentType.AMBIENT:
        return _generate_ambient_segment(segment, output_path)
    elif segment.type == SegmentType.PAUSE:
        return _generate_pause_segment(segment, output_path)
    return None


def _generate_voice_segment(
    segment: ScriptSegment,
    voice_map: dict[str, str],
    output_path: str,
) -> str | None:
    """Generate a voice segment (narration or dialogue)."""
    if not segment.text:
        return None

    character = segment.character or "narrator"
    voice_id = voice_map.get(character, voice_map.get("narrator", DEFAULT_NARRATOR_VOICE))
    preset = _tone_to_preset(segment.tone)

    generate_audio(segment.text, voice_id, output_path=output_path, preset=preset)
    return output_path


def _generate_sfx_segment(
    segment: ScriptSegment,
    output_path: str,
) -> str | None:
    """Generate a sound effect segment."""
    if not segment.description:
        return None

    generate_sfx(segment.description, output_path=output_path, duration_seconds=5.0)
    return output_path


def _generate_ambient_segment(
    segment: ScriptSegment,
    output_path: str,
) -> str | None:
    """Generate an ambient sound segment."""
    if not segment.description:
        return None

    duration = 10.0 if segment.loop else 5.0
    generate_sfx(segment.description, output_path=output_path, duration_seconds=duration)
    return output_path


def _generate_pause_segment(
    segment: ScriptSegment,
    output_path: str,
) -> str | None:
    """Generate a silence segment of the specified duration."""
    duration_ms = segment.duration_ms or 1500
    silence = AudioSegment.silent(duration=duration_ms)
    silence.export(output_path, format="mp3")
    return output_path


def _group_consecutive_segments(
    segments: list[ScriptSegment],
) -> list[ScriptSegment]:
    """Merge consecutive voice segments from the same character into single segments.

    When a character has multiple NARRATION or DIALOGUE lines in a row with no
    breaks (pause, SFX, ambient, or different character) between them, those
    lines are concatenated into one segment. This produces more natural-sounding
    TTS because ElevenLabs can read the combined text with proper flow rather
    than treating each line as an independent utterance.

    The merged segment uses the first segment's type and tone as the primary
    preset. If tones differ across the group, a combined tone description is
    built so the TTS model has context about the emotional arc.
    """
    if not segments:
        return []

    grouped: list[ScriptSegment] = []
    i = 0

    while i < len(segments):
        seg = segments[i]

        # Only group voice segments (narration/dialogue)
        if seg.type not in (SegmentType.NARRATION, SegmentType.DIALOGUE):
            grouped.append(seg)
            i += 1
            continue

        # Collect consecutive same-character voice segments
        group = [seg]
        j = i + 1
        while j < len(segments):
            next_seg = segments[j]
            if (next_seg.type in (SegmentType.NARRATION, SegmentType.DIALOGUE)
                    and next_seg.character == seg.character):
                group.append(next_seg)
                j += 1
            else:
                break

        if len(group) == 1:
            grouped.append(seg)
        else:
            # Merge: concatenate text, build combined tone description
            merged_text = " ".join(g.text for g in group if g.text)

            # Build tone: if all tones are the same (or None), use the first.
            # If they differ, describe the shift so TTS has emotional context.
            tones = [g.tone for g in group if g.tone]
            unique_tones = list(dict.fromkeys(tones))  # preserve order, dedupe
            if len(unique_tones) <= 1:
                merged_tone = unique_tones[0] if unique_tones else seg.tone
            else:
                merged_tone = " shifting to ".join(unique_tones)

            merged = ScriptSegment(
                type=seg.type,
                character=seg.character,
                text=merged_text,
                tone=merged_tone,
            )
            logger.info(
                f"Merged {len(group)} consecutive segments for "
                f"'{seg.character}' into one ({len(merged_text)} chars)"
            )
            grouped.append(merged)

        i = j

    return grouped


def _tone_to_preset(tone: str | None) -> str:
    """Map a tone description from the script to an ElevenLabs voice preset."""
    if not tone:
        return "horror_narrator"

    tone_lower = tone.lower()
    # Check high-intensity cues first so they take priority in merged tone strings
    # (e.g. "calm shifting to panicked" should yield horror_dialogue, not calm)
    if any(word in tone_lower for word in ["panic", "scream", "shout", "frantic", "desperate", "terrified"]):
        return "horror_dialogue"
    if any(word in tone_lower for word in ["whisper", "quiet", "hushed", "soft"]):
        return "whisper"
    if any(word in tone_lower for word in ["calm", "steady", "composed", "matter-of-fact"]):
        return "calm"
    return "horror_narrator"
