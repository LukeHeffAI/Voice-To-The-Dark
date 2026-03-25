"""Settings API endpoints for Django Ninja.

Ported from app/routers/settings.py — JSON API endpoints only (no HTML templates).
"""

import json
import logging

from django.http import FileResponse
from ninja import Router, UploadedFile, File, Form
from ninja.errors import HttpError

from apps.accounts.auth import get_current_user
from apps.stories.models import AppSetting
from services.elevenlabs import ElevenLabsError, generate_voice_preview
from services.reddit import get_cache_info, get_cache_path_for_timeframe
from services.voice_pool import VOICE_POOL


def _parse_json_body(request) -> dict:
    """Parse the request body as JSON dict."""
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        raise HttpError(400, "Invalid JSON body")
    if not isinstance(data, dict):
        raise HttpError(400, "Expected a JSON object")
    return data

logger = logging.getLogger(__name__)

router = Router()

# Valid timeframes for Reddit cache upload
VALID_TIMEFRAMES = ("alltime", "year", "month", "week", "today")

DEFAULT_TTL = 604800  # 1 week


def _get_voice_notes() -> dict[str, str]:
    """Load voice notes from AppSetting as a dict of voice_id -> note."""
    raw = AppSetting.get("voice_notes", "{}")
    try:
        notes = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        notes = {}
    if not isinstance(notes, dict):
        return {}
    sanitized: dict[str, str] = {}
    for key, value in notes.items():
        if isinstance(key, str) and isinstance(value, str):
            sanitized[key] = value
    return sanitized


@router.get("/api")
def get_settings(request):
    """Get all application settings as JSON."""
    get_current_user(request)
    settings = {s.key: s.value for s in AppSetting.objects.all()}
    settings.setdefault("reddit_cache_ttl", str(DEFAULT_TTL))
    return settings


@router.put("/api")
def update_settings(request):
    """Update application settings from a JSON body."""
    get_current_user(request)
    body = _parse_json_body(request)
    allowed_keys = {"reddit_cache_ttl"}
    updated = {}

    for key, value in body.items():
        if key not in allowed_keys:
            continue
        if key == "reddit_cache_ttl":
            try:
                ttl_val = int(value)
                if ttl_val < 60:
                    raise ValueError("TTL must be at least 60 seconds")
            except (ValueError, TypeError) as e:
                raise HttpError(400, f"Invalid value for {key}: {e}")
            value = str(ttl_val)

        AppSetting.set(key, value)
        updated[key] = value

    return {"updated": updated}


@router.post("/upload-reddit-cache")
def upload_reddit_cache(
    request,
    timeframe: str = Form(...),
    file: UploadedFile = File(...),
):
    """Upload a Reddit .json file to populate the disk cache for a timeframe."""
    get_current_user(request)

    if timeframe not in VALID_TIMEFRAMES:
        raise HttpError(
            400,
            f"Invalid timeframe. Must be one of: {', '.join(VALID_TIMEFRAMES)}",
        )

    content = file.read()
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise HttpError(400, f"Invalid JSON file: {e}")

    if not isinstance(data, dict) or "data" not in data:
        raise HttpError(
            400,
            "JSON does not look like a Reddit listing response (expected 'data' key)",
        )

    inner = data["data"]
    if not isinstance(inner, dict) or not isinstance(inner.get("children"), list):
        raise HttpError(
            400,
            "JSON does not look like a Reddit listing response (expected 'data.children' array)",
        )

    cache_path = get_cache_path_for_timeframe(timeframe)
    cache_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    children_count = len(inner["children"])
    logger.info("Uploaded Reddit cache for timeframe '%s': %d posts", timeframe, children_count)

    return {
        "status": "ok",
        "timeframe": timeframe,
        "posts_count": children_count,
    }


@router.get("/voice-notes")
def get_voice_notes(request):
    """Get all voice notes as a dict of voice_id -> note string."""
    get_current_user(request)
    return _get_voice_notes()


@router.put("/voice-notes")
def update_voice_notes(request):
    """Update voice notes. Body should be a dict of voice_id -> note string."""
    get_current_user(request)
    body = _parse_json_body(request)
    valid_voice_ids = {v.voice_id for v in VOICE_POOL}

    existing = _get_voice_notes()
    for voice_id, note in body.items():
        if voice_id not in valid_voice_ids:
            continue
        if not isinstance(note, str):
            continue
        note = note.strip()
        if note:
            existing[voice_id] = note
        else:
            existing.pop(voice_id, None)

    AppSetting.set("voice_notes", json.dumps(existing))
    return {"notes": existing}


@router.get("/voices")
def list_voices(request):
    """Return the curated voice pool as JSON."""
    get_current_user(request)
    return [
        {
            "voice_id": v.voice_id,
            "name": v.name,
            "gender": v.gender,
            "age": v.age,
            "archetypes": v.archetypes,
            "role": v.role,
        }
        for v in VOICE_POOL
    ]


@router.get("/voice-preview/{voice_id}")
def voice_preview(request, voice_id: str):
    """Generate or return a cached voice preview sample for the given voice."""
    get_current_user(request)
    valid_voice_ids = {v.voice_id: v.model for v in VOICE_POOL}
    if voice_id not in valid_voice_ids:
        raise HttpError(404, "Voice not found in pool")

    try:
        preview_path = generate_voice_preview(voice_id, model=valid_voice_ids[voice_id])
    except ElevenLabsError as exc:
        raise HttpError(502, f"Failed to generate voice preview: {exc}")

    return FileResponse(preview_path, content_type="audio/mpeg")
