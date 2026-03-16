import logging
import os
from urllib.parse import urlparse

from ninja import Router
from ninja.errors import HttpError

from apps.accounts.auth import JWTAuth
from apps.audio.schemas import NarrationScript, SegmentType
from apps.audio.services.elevenlabs import ElevenLabsError
from apps.audio.services.elevenlabs import generate_audio as elevenlabs_generate_audio
from apps.audio.services.narration_generator import generate_narration
from apps.audio.services.script_adapter import generate_script
from apps.audio.services.voice_pool import auto_assign_voices
from apps.core.rate_limit import check_rate_limit
from apps.stories.models import Story
from apps.stories.schemas import (
    GenerateAudioRequest,
    GenerateNarrationRequest,
    GenerateScriptRequest,
)

logger = logging.getLogger(__name__)

router = Router(tags=["audio"])


def _collect_series_characters(story: Story) -> dict | None:
    """Merge character definitions from earlier parts of the same series.

    Returns a dict of {name: {voice_profile: ...}} suitable for passing
    as *prior_characters* to generate_script, or None if there are none.
    """
    if not story.series_json:
        return None

    # series_json is already a list (Django JSONField)
    series_parts = story.series_json
    if not isinstance(series_parts, list):
        return None

    # Find the current story's created_utc in the series
    current_url = (story.reddit_url or "").rstrip("/")
    current_created = None
    for part in series_parts:
        part_url = (part.get("url") or "").rstrip("/")
        pa = urlparse(current_url)
        pb = urlparse(part_url)
        na = pa.netloc.lower().removeprefix("www.")
        nb = pb.netloc.lower().removeprefix("www.")
        if na == nb and pa.path.rstrip("/") == pb.path.rstrip("/"):
            current_created = part.get("created_utc", 0)
            break

    if current_created is None:
        return None

    # Collect URLs of earlier parts (by created_utc)
    earlier_urls = []
    for part in series_parts:
        if part.get("created_utc", 0) < current_created:
            url = (part.get("url") or "").strip()
            if url:
                earlier_urls.append(url)

    if not earlier_urls:
        return None

    # Build candidate URL set with host variants
    candidate_urls = set()
    for url in earlier_urls:
        base = url.rstrip("/")
        candidate_urls.add(base)
        candidate_urls.add(base + "/")
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            alt = netloc[4:] if netloc.startswith("www.") else "www." + netloc
            alt_url = parsed._replace(netloc=alt).geturl().rstrip("/")
            candidate_urls.add(alt_url)
            candidate_urls.add(alt_url + "/")
        except Exception:
            pass

    earlier_stories = list(Story.objects.filter(reddit_url__in=candidate_urls).exclude(script_json__isnull=True))

    if not earlier_stories:
        return None

    # Build a URL→created_utc lookup from series_parts for sorting
    url_to_created = {}
    for part in series_parts:
        pu = (part.get("url") or "").rstrip("/")
        p = urlparse(pu)
        key = (p.netloc.lower().removeprefix("www."), p.path.rstrip("/"))
        url_to_created[key] = part.get("created_utc", 0)

    def _sort_key(s: Story) -> float:
        p = urlparse((s.reddit_url or "").rstrip("/"))
        key = (p.netloc.lower().removeprefix("www."), p.path.rstrip("/"))
        return url_to_created.get(key, 0)

    earlier_stories.sort(key=_sort_key)

    # Merge character definitions (later parts override earlier)
    merged: dict = {}
    for s in earlier_stories:
        try:
            # script_json is already a dict (Django JSONField)
            script = NarrationScript(**s.script_json)
            merged.update({k: v.model_dump() for k, v in script.characters.items()})
        except Exception:
            continue

    return merged if merged else None


def _delete_audio_file(path: str | None) -> None:
    """Delete an audio file from disk if it exists."""
    if not path:
        return
    try:
        if os.path.exists(path):
            os.remove(path)
            logger.info("Deleted old audio file: %s", path)
    except Exception:
        logger.warning("Failed to delete old audio file: %s", path, exc_info=True)


@router.post("/generate-audio", auth=JWTAuth())
def generate_audio_route(request, payload: GenerateAudioRequest):
    """Generate basic TTS audio from the cleaned narration text (flat, single voice)."""
    story = Story.objects.filter(id=payload.story_id).first()
    if not story:
        raise HttpError(404, "Story not found")

    if story.audio_file_path and not payload.force_regenerate:
        return {"message": "Already generated", "audio_file": story.audio_file_path}

    tts_text = story.narration_text or story.text_content
    try:
        new_audio_path = elevenlabs_generate_audio(tts_text, payload.voice_id)
    except ElevenLabsError as exc:
        logger.exception("ElevenLabs audio generation failed for story %s", payload.story_id)
        raise HttpError(502, f"Audio generation failed: {exc}") from exc
    except Exception as exc:
        logger.exception("Unexpected error generating audio for story %s", payload.story_id)
        raise HttpError(500, f"Audio generation failed unexpectedly: {exc}") from exc

    story.audio_file_path = new_audio_path
    story.save()

    return {"message": "Audio generated successfully!", "audio_file": story.audio_file_path}


@router.post("/generate-script", auth=JWTAuth())
def generate_script_route(request, payload: GenerateScriptRequest):
    """Use Claude to transform a story into a dramatic narration script."""
    check_rate_limit(request.auth.id, max_requests=10, window_seconds=3600)

    story = Story.objects.filter(id=payload.story_id).first()
    if not story:
        raise HttpError(404, "Story not found")

    if story.script_json and not payload.force_regenerate:
        # script_json is already a dict (Django JSONField)
        script = NarrationScript(**story.script_json)
        return {
            "message": "Script already exists",
            "script": script.model_dump(),
            "characters": script.character_names(),
        }

    text = story.narration_text or story.text_content
    if not text:
        raise HttpError(400, "Story has no text to adapt")

    prior_characters = _collect_series_characters(story)

    try:
        script = generate_script(story.title, text, prior_characters=prior_characters)
    except Exception as exc:
        logger.exception("Script generation failed for story %s", payload.story_id)
        raise HttpError(502, f"Script generation failed: {exc}") from exc

    # Store as dict (Django JSONField handles serialization)
    story.script_json = script.model_dump()
    story.save()

    return {
        "message": "Script generated successfully!",
        "script": script.model_dump(),
        "characters": script.character_names(),
    }


@router.get("/script/{story_id}")
def get_script(request, story_id: int):
    """Retrieve the narration script for a story."""
    story = Story.objects.filter(id=story_id).first()
    if not story:
        raise HttpError(404, "Story not found")

    if not story.script_json:
        raise HttpError(404, "No script generated for this story yet")

    script = NarrationScript(**story.script_json)
    return {
        "script": script.model_dump(),
        "characters": script.character_names(),
        "segment_count": len(script.segments),
        "voice_segments": len(script.voice_segments()),
        "sfx_segments": len(script.sfx_segments()),
    }


@router.put("/script/{story_id}", auth=JWTAuth())
def update_script(request, story_id: int, script_data: dict):
    """Update/edit the narration script before generating audio."""
    story = Story.objects.filter(id=story_id).first()
    if not story:
        raise HttpError(404, "Story not found")

    script = NarrationScript(**script_data)

    # Validate that segment characters exist in the characters dict
    character_names = set(script.characters.keys())
    unknown_characters = set()
    for seg in script.segments:
        if seg.type in (SegmentType.NARRATION, SegmentType.DIALOGUE) and seg.character:
            if seg.character not in character_names:
                unknown_characters.add(seg.character)
    if unknown_characters:
        raise HttpError(
            400,
            f"Segments reference undefined characters: {sorted(unknown_characters)}. "
            f"Defined characters: {sorted(character_names)}",
        )

    # Invalidate stale audio
    _delete_audio_file(story.audio_file_path)
    story.audio_file_path = None
    story.script_json = script.model_dump()
    story.save()

    return {"message": "Script updated", "characters": script.character_names()}


@router.post("/generate-narration", auth=JWTAuth())
def generate_narration_route(request, payload: GenerateNarrationRequest):
    """Generate the full dramatic narration: multi-voice TTS + SFX + ambient + mixing."""
    check_rate_limit(request.auth.id, max_requests=5, window_seconds=3600)

    story = Story.objects.filter(id=payload.story_id).first()
    if not story:
        raise HttpError(404, "Story not found")

    if story.audio_file_path and not payload.force_regenerate:
        return {"message": "Already generated", "audio_file": story.audio_file_path}

    if not story.script_json:
        raise HttpError(400, "No script found. Generate a script first with /generate-script")

    script = NarrationScript(**story.script_json)

    # Auto-assign voices if no voice_map provided
    voice_map = payload.voice_map
    if not voice_map:
        voice_map = auto_assign_voices(script.characters)
        logger.info(f"Auto-assigned voices: {voice_map}")
    else:
        missing = [c for c in script.character_names() if c not in voice_map]
        if missing:
            raise HttpError(
                400,
                f"Missing voice assignments for characters: {missing}. Required characters: {script.character_names()}",
            )

    # Persist voice IDs into character profiles
    for char_name, voice_id in voice_map.items():
        if char_name in script.characters:
            script.characters[char_name].voice_id = voice_id
    story.script_json = script.model_dump()

    # Clean up old audio file
    _delete_audio_file(story.audio_file_path)

    try:
        result = generate_narration(script, voice_map, bust_cache=payload.bust_cache)
    except ElevenLabsError as exc:
        logger.exception("ElevenLabs narration generation failed for story %s", payload.story_id)
        raise HttpError(502, f"Narration generation failed: {exc}") from exc
    except Exception as exc:
        logger.exception("Unexpected error generating narration for story %s", payload.story_id)
        raise HttpError(500, f"Narration generation failed unexpectedly: {exc}") from exc

    story.audio_file_path = result.output_path
    story.save()

    return {
        "message": "Narration generated successfully!",
        "audio_file": result.output_path,
        "segments_processed": result.total_segments,
        "voice_assignments": voice_map,
        "cache_stats": {
            "total_segments": result.total_segments,
            "cache_hits": result.cache_hits,
            "cache_misses": result.cache_misses,
            "api_calls_saved": result.cache_hits,
        },
    }
