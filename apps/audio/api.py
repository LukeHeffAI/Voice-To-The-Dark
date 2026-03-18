"""Audio API endpoints for Django Ninja.

Ported from app/routers/audio.py — script generation, audio generation, narration.
"""

import logging
import os
from urllib.parse import urlparse

from ninja import Router
from django.db import IntegrityError
from ninja.errors import HttpError

from apps.accounts.auth import get_current_user
from apps.audio.helpers import pydantic_to_script, script_to_pydantic
from apps.audio.models import NarrationScript as NarrationScriptModel
from apps.common.rate_limit import check_rate_limit
from apps.stories.models import Story
from schemas.narration import NarrationScript, SegmentType
from schemas.story import GenerateAudioRequest, GenerateNarrationRequest, GenerateScriptRequest
from services.elevenlabs import ElevenLabsError, generate_audio
from services.voice_pool import auto_assign_voices

logger = logging.getLogger(__name__)

router = Router()


def _collect_series_characters(story: Story) -> dict | None:
    """Merge character definitions from earlier parts of the same series.

    Returns a dict of {name: {voice_profile: ...}} or None.
    """
    if not story.series_json:
        return None

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

    # Find earlier stories that have scripts
    earlier_stories = list(
        Story.objects.filter(reddit_url__in=candidate_urls)
        .select_related()
        .all()
    )

    # Filter to stories that have a script in the relational model
    stories_with_scripts = []
    for s in earlier_stories:
        try:
            if hasattr(s, "script") and s.script is not None:
                stories_with_scripts.append(s)
        except NarrationScriptModel.DoesNotExist:
            pass

    if not stories_with_scripts:
        return None

    # Build a URL→created_utc lookup for sorting
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

    stories_with_scripts.sort(key=_sort_key)

    # Merge character definitions (later parts override earlier)
    merged: dict = {}
    for s in stories_with_scripts:
        try:
            pydantic_script = script_to_pydantic(s.script)
            merged.update({k: v.model_dump() for k, v in pydantic_script.characters.items()})
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


def _get_story_script(story: Story) -> NarrationScript | None:
    """Get the Pydantic NarrationScript for a story, or None."""
    try:
        db_script = story.script
        if db_script is None:
            return None
        return script_to_pydantic(db_script)
    except NarrationScriptModel.DoesNotExist:
        return None


@router.post("/generate-audio")
def generate_audio_route(request, payload: GenerateAudioRequest):
    """Generate basic TTS audio from the cleaned narration text (single voice)."""
    get_current_user(request)

    story = Story.objects.filter(id=payload.story_id).first()
    if not story:
        raise HttpError(404, "Story not found")

    if story.audio_file_path and not payload.force_regenerate:
        return {"message": "Already generated", "audio_file": story.audio_file_path}

    tts_text = story.narration_text or story.text_content
    try:
        new_audio_path = generate_audio(tts_text, payload.voice_id)
    except ElevenLabsError as exc:
        logger.exception("ElevenLabs audio generation failed for story %s", payload.story_id)
        raise HttpError(502, f"Audio generation failed: {exc}")
    except Exception as exc:
        logger.exception("Unexpected error generating audio for story %s", payload.story_id)
        raise HttpError(500, f"Audio generation failed unexpectedly: {exc}")

    story.audio_file_path = new_audio_path
    story.save(update_fields=["audio_file_path"])

    return {
        "message": "Audio generated successfully!",
        "audio_file": story.audio_file_path,
    }


@router.post("/generate-script")
def generate_script_route(request, payload: GenerateScriptRequest):
    """Use Claude to transform a story into a dramatic narration script."""
    user = get_current_user(request)
    check_rate_limit(user.id, 10, 3600)

    story = Story.objects.filter(id=payload.story_id).first()
    if not story:
        raise HttpError(404, "Story not found")

    existing_script = _get_story_script(story)
    if existing_script and not payload.force_regenerate:
        return {
            "message": "Script already exists",
            "script": existing_script.model_dump(),
            "characters": existing_script.character_names(),
        }

    text = story.narration_text or story.text_content
    if not text:
        raise HttpError(400, "Story has no text to adapt")

    prior_characters = _collect_series_characters(story)

    # Submit as background task
    from apps.tasks.executor import submit_task
    from apps.tasks.models import ACTIVE_STATUSES, BackgroundTask, TaskType
    from apps.tasks.task_functions import run_generate_script

    try:
        task = BackgroundTask.objects.create(
            user=user,
            story=story,
            task_type=TaskType.GENERATE_SCRIPT,
            progress_message="Queued for processing...",
        )
    except IntegrityError:
        existing = BackgroundTask.objects.filter(
            story=story,
            task_type=TaskType.GENERATE_SCRIPT,
            status__in=[s.value for s in ACTIVE_STATUSES],
        ).first()
        if existing:
            return {"task_id": existing.id, "message": "Script generation already in progress"}
        raise HttpError(409, "A script generation task is already active for this story")
    submit_task(task.id, run_generate_script, story.id, prior_characters)

    return {"task_id": task.id, "message": "Script generation started"}


@router.get("/script/{story_id}")
def get_script(request, story_id: int):
    """Retrieve the narration script for a story."""
    story = Story.objects.filter(id=story_id).first()
    if not story:
        raise HttpError(404, "Story not found")

    script = _get_story_script(story)
    if not script:
        raise HttpError(404, "No script generated for this story yet")

    return {
        "script": script.model_dump(),
        "characters": script.character_names(),
        "segment_count": len(script.segments),
        "voice_segments": len(script.voice_segments()),
        "sfx_segments": len(script.sfx_segments()),
    }


@router.put("/script/{story_id}")
def update_script(request, story_id: int):
    """Update/edit the narration script before generating audio."""
    import json as _json

    get_current_user(request)

    story = Story.objects.filter(id=story_id).first()
    if not story:
        raise HttpError(404, "Story not found")

    # Parse request body as JSON
    try:
        script_data = _json.loads(request.body)
    except (ValueError, _json.JSONDecodeError):
        raise HttpError(400, "Invalid JSON body")

    # Validate the script structure
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
    story.audio_file_path = ""
    story.save(update_fields=["audio_file_path"])

    # Save to relational models
    pydantic_to_script(story, script)

    return {"message": "Script updated", "characters": script.character_names()}


@router.post("/generate-narration")
def generate_narration_route(request, payload: GenerateNarrationRequest):
    """Generate the full dramatic narration: multi-voice TTS + SFX + ambient + mixing."""
    user = get_current_user(request)
    check_rate_limit(user.id, 5, 3600)

    story = Story.objects.filter(id=payload.story_id).first()
    if not story:
        raise HttpError(404, "Story not found")

    if story.audio_file_path and not payload.force_regenerate:
        return {"message": "Already generated", "audio_file": story.audio_file_path}

    script = _get_story_script(story)
    if not script:
        raise HttpError(400, "No script found. Generate a script first with /generate-script")

    # Auto-assign voices if no voice_map provided
    voice_map = payload.voice_map
    if not voice_map:
        voice_map = auto_assign_voices(script.characters)
        logger.info("Auto-assigned voices: %s", voice_map)
    else:
        missing = [c for c in script.character_names() if c not in voice_map]
        if missing:
            raise HttpError(
                400,
                f"Missing voice assignments for characters: {missing}. "
                f"Required characters: {script.character_names()}",
            )

    # Persist voice IDs into character profiles
    for char_name, voice_id in voice_map.items():
        if char_name in script.characters:
            script.characters[char_name].voice_id = voice_id
    pydantic_to_script(story, script)

    # Submit as background task
    from apps.tasks.executor import submit_task
    from apps.tasks.models import ACTIVE_STATUSES, BackgroundTask, TaskType
    from apps.tasks.task_functions import run_generate_narration

    try:
        task = BackgroundTask.objects.create(
            user=user,
            story=story,
            task_type=TaskType.GENERATE_NARRATION,
            progress_message="Queued for processing...",
        )
    except IntegrityError:
        existing = BackgroundTask.objects.filter(
            user=user,
            story=story,
            task_type=TaskType.GENERATE_NARRATION,
            status__in=[s.value for s in ACTIVE_STATUSES],
        ).first()
        if existing:
            return {"task_id": existing.id, "message": "Narration generation already in progress"}
        raise HttpError(409, "A narration generation task is already active for this story")
    submit_task(
        task.id,
        run_generate_narration,
        story.id,
        voice_map,
        script.model_dump(),
        payload.bust_cache,
    )

    return {"task_id": task.id, "message": "Narration generation started"}
