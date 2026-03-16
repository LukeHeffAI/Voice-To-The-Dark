import logging
from dataclasses import dataclass, field

from pydub import AudioSegment

from apps.audio.schemas import ScriptSegment, SegmentType

logger = logging.getLogger(__name__)

# --- Mix configuration ---

AMBIENT_VOLUME_DB = -20  # ambient bed sits well below voice
SFX_VOLUME_DB = -6  # SFX are prominent but don't overpower
CROSSFADE_MS = 100  # crossfade between consecutive voice segments
INTRO_FADE_MS = 2500  # ambient fades in at the start
OUTRO_FADE_MS = 3500  # everything fades out at the end
PAUSE_BETWEEN_SCENES_MS = 1800  # silence inserted at scene transitions
TARGET_LOUDNESS_DBFS = -18.0  # target integrated loudness for normalization


@dataclass
class TimelineEntry:
    """A positioned piece of audio on the mix timeline."""

    audio: AudioSegment
    segment: ScriptSegment
    position_ms: int = 0  # absolute start position on the timeline


@dataclass
class MixTimeline:
    """Collects all audio segments into a timeline for mixing."""

    voice_track: list[TimelineEntry] = field(default_factory=list)
    sfx_entries: list[TimelineEntry] = field(default_factory=list)
    ambient_entries: list[TimelineEntry] = field(default_factory=list)
    total_duration_ms: int = 0


def mix_narration(
    segment_files: list[tuple[str, ScriptSegment]],
) -> AudioSegment:
    """Take generated audio files + their script segments and produce a fully
    mixed audio production.

    Mixing stages:
      1. Build the voice track (narration + dialogue + pauses in sequence)
      2. Place SFX at their timeline positions
      3. Build a continuous ambient bed that spans each scene
      4. Layer ambient underneath voice, overlay SFX on top
      5. Add intro fade-in and outro fade-out
      6. Normalize loudness
    """
    if not segment_files:
        return AudioSegment.silent(duration=1000)

    timeline = _build_timeline(segment_files)
    mixed = _render_timeline(timeline)
    mixed = _apply_fades(mixed, timeline)
    mixed = _normalize(mixed)

    logger.info(
        f"Mix complete: {len(mixed)}ms, "
        f"{len(timeline.voice_track)} voice, "
        f"{len(timeline.sfx_entries)} sfx, "
        f"{len(timeline.ambient_entries)} ambient"
    )
    return mixed


# ---- Timeline construction ----


def _build_timeline(
    segment_files: list[tuple[str, ScriptSegment]],
) -> MixTimeline:
    """Walk through segments in script order and place them on a timeline.

    Voice and pause segments advance the playhead sequentially.
    SFX and ambient segments are placed at the current playhead position
    (they overlay, they don't push the timeline forward).
    """
    timeline = MixTimeline()
    playhead_ms = 0

    for path, segment in segment_files:
        audio = AudioSegment.from_file(path, format="mp3")

        if segment.type in (SegmentType.NARRATION, SegmentType.DIALOGUE):
            entry = TimelineEntry(audio=audio, segment=segment, position_ms=playhead_ms)
            timeline.voice_track.append(entry)
            playhead_ms += len(audio)

        elif segment.type == SegmentType.PAUSE:
            entry = TimelineEntry(audio=audio, segment=segment, position_ms=playhead_ms)
            timeline.voice_track.append(entry)
            playhead_ms += len(audio)

        elif segment.type == SegmentType.SFX:
            entry = TimelineEntry(audio=audio, segment=segment, position_ms=playhead_ms)
            timeline.sfx_entries.append(entry)
            # SFX occupies time on the timeline — listeners hear it before
            # the next voice line, so advance the playhead by its duration
            playhead_ms += len(audio)

        elif segment.type == SegmentType.AMBIENT:
            entry = TimelineEntry(audio=audio, segment=segment, position_ms=playhead_ms)
            timeline.ambient_entries.append(entry)
            # Ambient does NOT advance the playhead — it layers underneath

    timeline.total_duration_ms = playhead_ms
    return timeline


# ---- Rendering ----


def _render_timeline(timeline: MixTimeline) -> AudioSegment:
    """Render all timeline tracks into a single mixed AudioSegment."""

    duration = timeline.total_duration_ms
    if duration <= 0:
        return AudioSegment.silent(duration=1000)

    # Start with the voice track as the foundation
    voice_mix = _render_voice_track(timeline.voice_track, duration)

    # Build the ambient bed
    ambient_bed = _render_ambient_bed(timeline.ambient_entries, duration)

    # Build the SFX layer
    sfx_layer = _render_sfx_layer(timeline.sfx_entries, duration)

    # Layer: ambient underneath voice, SFX on top
    mixed = ambient_bed.overlay(voice_mix)
    mixed = mixed.overlay(sfx_layer)

    return mixed


def _render_voice_track(
    entries: list[TimelineEntry],
    duration_ms: int,
) -> AudioSegment:
    """Render voice and pause segments onto a silent canvas, applying
    crossfades between consecutive voice segments."""

    canvas = AudioSegment.silent(duration=duration_ms)

    prev_end_ms = None
    prev_type = None

    for entry in entries:
        audio = entry.audio
        pos = entry.position_ms

        # Apply crossfade if this voice segment directly follows another
        if (
            entry.segment.type in (SegmentType.NARRATION, SegmentType.DIALOGUE)
            and prev_type in (SegmentType.NARRATION, SegmentType.DIALOGUE)
            and prev_end_ms is not None
            and pos == prev_end_ms
        ):
            # Overlap the tail of the previous with the head of this one
            fade = min(CROSSFADE_MS, len(audio) // 2)
            if fade > 0:
                pos = max(0, pos - fade)

        canvas = canvas.overlay(audio, position=pos)

        if entry.segment.type != SegmentType.PAUSE:
            prev_end_ms = pos + len(audio)
            prev_type = entry.segment.type
        else:
            prev_type = SegmentType.PAUSE
            prev_end_ms = pos + len(audio)

    return canvas


def _render_ambient_bed(
    entries: list[TimelineEntry],
    duration_ms: int,
) -> AudioSegment:
    """Build a continuous ambient bed.

    Each ambient entry persists from its start position until the next ambient
    entry begins (scene change) or until the end of the production. The ambient
    is looped to fill its span and set to a low volume so it sits underneath
    the voice.
    """
    if not entries:
        return AudioSegment.silent(duration=duration_ms)

    bed = AudioSegment.silent(duration=duration_ms)

    for i, entry in enumerate(entries):
        start = entry.position_ms
        # This ambient runs until the next ambient starts, or end of production
        if i + 1 < len(entries):
            end = entries[i + 1].position_ms
        else:
            end = duration_ms

        span = end - start
        if span <= 0:
            continue

        # Loop the ambient clip to fill the span
        ambient = entry.audio
        if len(ambient) < span:
            repeats = (span // len(ambient)) + 1
            ambient = ambient * repeats
        ambient = ambient[:span]

        # Set volume and apply fade-in at the start of this ambient section
        ambient = ambient + AMBIENT_VOLUME_DB
        ambient = ambient.fade_in(min(1500, span // 2))

        # If this ambient section ends because a new one starts, fade out
        if i + 1 < len(entries):
            ambient = ambient.fade_out(min(1000, span // 2))

        bed = bed.overlay(ambient, position=start)

    return bed


def _render_sfx_layer(
    entries: list[TimelineEntry],
    duration_ms: int,
) -> AudioSegment:
    """Place SFX clips at their timeline positions with appropriate volume."""

    layer = AudioSegment.silent(duration=duration_ms)

    for entry in entries:
        sfx = entry.audio + SFX_VOLUME_DB
        # Fade SFX in/out briefly to avoid harsh cuts
        sfx = sfx.fade_in(min(50, len(sfx) // 4))
        sfx = sfx.fade_out(min(200, len(sfx) // 4))
        layer = layer.overlay(sfx, position=entry.position_ms)

    return layer


# ---- Post-processing ----


def _apply_fades(
    mixed: AudioSegment,
    timeline: MixTimeline,
) -> AudioSegment:
    """Apply intro fade-in and outro fade-out to the final mix."""

    # Intro: fade in over the first few seconds
    intro_ms = min(INTRO_FADE_MS, len(mixed) // 4)
    if intro_ms > 0:
        mixed = mixed.fade_in(intro_ms)

    # Outro: fade out over the last few seconds
    outro_ms = min(OUTRO_FADE_MS, len(mixed) // 4)
    if outro_ms > 0:
        mixed = mixed.fade_out(outro_ms)

    return mixed


def _normalize(mixed: AudioSegment) -> AudioSegment:
    """Normalize the loudness of the final mix to a consistent level.

    Uses a simple peak-based normalization targeting TARGET_LOUDNESS_DBFS.
    """
    if mixed.dBFS == float("-inf"):
        return mixed

    loudness_delta = TARGET_LOUDNESS_DBFS - mixed.dBFS
    # Clamp the adjustment to avoid extreme amplification of quiet audio
    loudness_delta = max(-12.0, min(12.0, loudness_delta))
    return mixed + loudness_delta
