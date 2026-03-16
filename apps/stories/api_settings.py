import json
import logging

from django.http import FileResponse
from ninja import Body, File, Router
from ninja.errors import HttpError
from ninja.files import UploadedFile

from apps.accounts.auth import JWTAuth
from apps.audio.services.elevenlabs import ElevenLabsError, generate_voice_preview
from apps.audio.services.voice_pool import VOICE_POOL
from apps.stories.models import AppSetting
from apps.stories.services.reddit import get_cache_path_for_timeframe

logger = logging.getLogger(__name__)

router = Router(tags=["settings"])

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


@router.get("/", auth=JWTAuth())
def get_settings(request):
    """Get all application settings as JSON."""
    settings_qs = AppSetting.objects.all()
    result = {s.key: s.value for s in settings_qs}
    result.setdefault("reddit_cache_ttl", str(DEFAULT_TTL))
    return result


@router.put("/", auth=JWTAuth())
def update_settings(request, body: dict = Body(...)):
    """Update application settings from a JSON body."""
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


@router.post("/upload-reddit-cache", auth=JWTAuth())
def upload_reddit_cache(request, timeframe: str, file: UploadedFile = File(...)):
    """Upload a Reddit .json file to populate the disk cache for a timeframe."""
    if timeframe not in VALID_TIMEFRAMES:
        raise HttpError(400, f"Invalid timeframe. Must be one of: {', '.join(VALID_TIMEFRAMES)}")

    content = file.read()
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise HttpError(400, f"Invalid JSON file: {e}")

    if not isinstance(data, dict) or "data" not in data:
        raise HttpError(400, "JSON does not look like a Reddit listing response (expected 'data' key)")

    cache_path = get_cache_path_for_timeframe(timeframe)
    cache_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    children_count = len(data.get("data", {}).get("children", []))
    logger.info("Uploaded Reddit cache for timeframe '%s': %d posts", timeframe, children_count)

    return {
        "status": "ok",
        "timeframe": timeframe,
        "posts_count": children_count,
    }


@router.get("/voice-notes", auth=JWTAuth())
def get_voice_notes(request):
    """Get all voice notes as a dict of voice_id -> note string."""
    return _get_voice_notes()


@router.put("/voice-notes", auth=JWTAuth())
def update_voice_notes(request, body: dict = Body(...)):
    """Update voice notes. Body should be a dict of voice_id -> note string."""
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


@router.get("/voice-preview/{voice_id}", auth=JWTAuth())
def voice_preview(request, voice_id: str):
    """Generate or return a cached voice preview sample for the given voice."""
    valid_voice_ids = {v.voice_id: v.model for v in VOICE_POOL}
    if voice_id not in valid_voice_ids:
        raise HttpError(404, "Voice not found in pool")

    try:
        preview_path = generate_voice_preview(voice_id, model=valid_voice_ids[voice_id])
    except ElevenLabsError as exc:
        raise HttpError(502, f"Failed to generate voice preview: {exc}") from exc

    return FileResponse(open(preview_path, "rb"), content_type="audio/mpeg")
