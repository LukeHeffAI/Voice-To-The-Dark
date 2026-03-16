import logging

from ninja import Router
from ninja.errors import HttpError

from apps.accounts.auth import JWTAuth
from apps.audio.models import GenerationTask
from apps.audio.schemas import (
    GenerationTaskResponse,
    NarrationScript,
    SegmentType,
    TaskStartResponse,
)
from apps.audio.services.elevenlabs import ElevenLabsError
from apps.audio.services.elevenlabs import generate_audio as elevenlabs_generate_audio
from apps.audio.services.voice_pool import auto_assign_voices
from apps.audio.task_runner import start_narration_generation, start_script_generation
from apps.core.rate_limit import check_rate_limit
from apps.stories.models import Story
from apps.stories.schemas import (
    GenerateAudioRequest,
    GenerateNarrationRequest,
    GenerateScriptRequest,
)

logger = logging.getLogger(__name__)

router = Router(tags=["audio"])


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


@router.post("/generate-script", auth=JWTAuth(), response=TaskStartResponse)
def generate_script_route(request, payload: GenerateScriptRequest):
    """Launch background script generation and return a task ID for polling."""
    check_rate_limit(request.auth.id, max_requests=10, window_seconds=3600)

    story = Story.objects.filter(id=payload.story_id).first()
    if not story:
        raise HttpError(404, "Story not found")

    if story.script_json and not payload.force_regenerate:
        script = NarrationScript(**story.script_json)
        # Return a synthetic completed task so the frontend can handle it uniformly
        task = GenerationTask.objects.create(
            user=request.auth,
            story=story,
            task_type="script",
            status="completed",
            progress=100,
            stage="Script already exists",
            result_json={
                "message": "Script already exists",
                "characters": script.character_names(),
            },
        )
        return {"task_id": task.id}

    text = story.narration_text or story.text_content
    if not text:
        raise HttpError(400, "Story has no text to adapt")

    # Check for already-running task
    active = GenerationTask.objects.filter(
        story=story, task_type="script", status__in=["queued", "running"]
    ).first()
    if active:
        return {"task_id": active.id}

    task = GenerationTask.objects.create(
        user=request.auth,
        story=story,
        task_type="script",
        status="queued",
        stage="Queued",
    )
    start_script_generation(task)
    return {"task_id": task.id}


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
    import os

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
    if story.audio_file_path:
        try:
            if os.path.exists(story.audio_file_path):
                os.remove(story.audio_file_path)
        except Exception:
            logger.warning("Failed to delete old audio: %s", story.audio_file_path, exc_info=True)
    story.audio_file_path = None
    story.script_json = script.model_dump()
    story.save()

    return {"message": "Script updated", "characters": script.character_names()}


@router.post("/generate-narration", auth=JWTAuth(), response=TaskStartResponse)
def generate_narration_route(request, payload: GenerateNarrationRequest):
    """Launch background narration generation and return a task ID for polling."""
    check_rate_limit(request.auth.id, max_requests=5, window_seconds=3600)

    story = Story.objects.filter(id=payload.story_id).first()
    if not story:
        raise HttpError(404, "Story not found")

    if story.audio_file_path and not payload.force_regenerate:
        # Return a synthetic completed task
        task = GenerationTask.objects.create(
            user=request.auth,
            story=story,
            task_type="narration",
            status="completed",
            progress=100,
            stage="Already generated",
            result_json={"message": "Already generated", "audio_file": story.audio_file_path},
        )
        return {"task_id": task.id}

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
                f"Missing voice assignments for characters: {missing}. "
                f"Required characters: {script.character_names()}",
            )

    # Check for already-running task
    active = GenerationTask.objects.filter(
        story=story, task_type="narration", status__in=["queued", "running"]
    ).first()
    if active:
        return {"task_id": active.id}

    task = GenerationTask.objects.create(
        user=request.auth,
        story=story,
        task_type="narration",
        status="queued",
        stage="Queued",
    )
    start_narration_generation(task, voice_map, bust_cache=payload.bust_cache)
    return {"task_id": task.id}


@router.get("/tasks/{task_id}", auth=JWTAuth(), response=GenerationTaskResponse)
def get_task_status(request, task_id: int):
    """Poll for task progress."""
    task = GenerationTask.objects.filter(id=task_id, user=request.auth).first()
    if not task:
        raise HttpError(404, "Task not found")

    return GenerationTaskResponse(
        id=task.id,
        task_type=task.task_type,
        status=task.status,
        progress=task.progress,
        stage=task.stage,
        result=task.result_json,
        error_message=task.error_message,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
    )


@router.get("/tasks/active/{story_id}", auth=JWTAuth(), response=GenerationTaskResponse)
def get_active_task(request, story_id: int):
    """Check if a story has an active (queued/running) generation task."""
    task = (
        GenerationTask.objects.filter(
            story_id=story_id,
            user=request.auth,
            status__in=["queued", "running"],
        )
        .order_by("-created_at")
        .first()
    )
    if not task:
        raise HttpError(404, "No active task")

    return GenerationTaskResponse(
        id=task.id,
        task_type=task.task_type,
        status=task.status,
        progress=task.progress,
        stage=task.stage,
        result=task.result_json,
        error_message=task.error_message,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
    )
