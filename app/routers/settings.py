import json
import logging
import os
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.app_setting import AppSetting, get_setting, set_setting
from app.models.story import User
from app.deps import get_current_user, get_optional_user
from app.services.reddit import get_cache_path_for_timeframe, get_cache_info
from app.services.voice_pool import VOICE_POOL
from app.services.elevenlabs import generate_voice_preview, ElevenLabsError

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
)

# Valid timeframes for Reddit cache upload
VALID_TIMEFRAMES = ("alltime", "year", "month", "week", "today")

# Predefined TTL options (seconds) for the settings dropdown
TTL_OPTIONS = [
    (3600, "1 hour"),
    (21600, "6 hours"),
    (86400, "1 day"),
    (259200, "3 days"),
    (604800, "1 week"),
    (1209600, "2 weeks"),
    (2592000, "1 month"),
]

DEFAULT_TTL = 604800  # 1 week


def _get_voice_notes(db: Session) -> dict[str, str]:
    """Load voice notes from AppSetting as a dict of voice_id -> note."""
    raw = get_setting(db, "voice_notes", "{}")
    try:
        notes = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        notes = {}
    # Ensure we always return a dict[str, str]
    if not isinstance(notes, dict):
        return {}
    sanitized: dict[str, str] = {}
    for key, value in notes.items():
        if isinstance(key, str) and isinstance(value, str):
            sanitized[key] = value
    return sanitized


@router.get("/", response_class=HTMLResponse)
def settings_page(request: Request, db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)):
    """Serve the settings page."""
    if not user:
        return templates.TemplateResponse("login.html", {"request": request})

    current_ttl = int(get_setting(db, "reddit_cache_ttl", str(DEFAULT_TTL)))
    cache_info = get_cache_info()

    voice_notes = _get_voice_notes(db)
    voice_pool_json = [
        {
            "voice_id": v.voice_id,
            "name": v.name,
            "gender": v.gender,
            "age": v.age,
            "role": v.role,
            "archetypes": v.archetypes,
            "notes": voice_notes.get(v.voice_id, ""),
            "model": v.model,
        }
        for v in VOICE_POOL
    ]

    return templates.TemplateResponse("settings.html", {
        "request": request,
        "user": user,
        "current_ttl": current_ttl,
        "ttl_options": TTL_OPTIONS,
        "cache_info": cache_info,
        "timeframes": VALID_TIMEFRAMES,
        "voice_pool_json": voice_pool_json,
    })


@router.get("/api")
def get_settings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Get all application settings as JSON."""
    settings = db.query(AppSetting).all()
    result = {s.key: s.value for s in settings}
    # Include defaults for keys not yet in DB
    result.setdefault("reddit_cache_ttl", str(DEFAULT_TTL))
    return result


@router.put("/api")
def update_settings(body: dict, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Update application settings from a JSON body."""
    allowed_keys = {"reddit_cache_ttl"}
    updated = {}

    for key, value in body.items():
        if key not in allowed_keys:
            continue
        # Validate TTL is a positive integer
        if key == "reddit_cache_ttl":
            try:
                ttl_val = int(value)
                if ttl_val < 60:
                    raise ValueError("TTL must be at least 60 seconds")
            except (ValueError, TypeError) as e:
                raise HTTPException(status_code=400, detail=f"Invalid value for {key}: {e}")
            value = str(ttl_val)

        set_setting(db, key, value)
        updated[key] = value

    return {"updated": updated}


@router.post("/upload-reddit-cache")
async def upload_reddit_cache(
    timeframe: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Upload a Reddit .json file to populate the disk cache for a timeframe.

    This allows manually downloading Reddit JSON data and uploading it
    when Reddit is unreachable from the server.
    """
    if timeframe not in VALID_TIMEFRAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timeframe. Must be one of: {', '.join(VALID_TIMEFRAMES)}"
        )

    # Read and validate the uploaded JSON
    content = await file.read()
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON file: {e}")

    # Basic structure validation — Reddit listing responses have data.children
    if not isinstance(data, dict) or "data" not in data:
        raise HTTPException(
            status_code=400,
            detail="JSON does not look like a Reddit listing response (expected 'data' key)"
        )

    # Write to the correct cache location
    cache_path = get_cache_path_for_timeframe(timeframe)
    cache_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    children_count = len(data.get("data", {}).get("children", []))
    logger.info("Uploaded Reddit cache for timeframe '%s': %d posts", timeframe, children_count)

    return {
        "status": "ok",
        "timeframe": timeframe,
        "posts_count": children_count,
    }


@router.get("/voice-notes")
def get_voice_notes(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Get all voice notes as a dict of voice_id -> note string."""
    return _get_voice_notes(db)


@router.put("/voice-notes")
def update_voice_notes(body: dict, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Update voice notes. Body should be a dict of voice_id -> note string."""
    valid_voice_ids = {v.voice_id for v in VOICE_POOL}

    # Load existing notes and merge
    existing = _get_voice_notes(db)
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

    set_setting(db, "voice_notes", json.dumps(existing))
    return {"notes": existing}


@router.get("/voice-preview/{voice_id}")
def voice_preview(voice_id: str, user: User = Depends(get_current_user)):
    """Generate or return a cached voice preview sample for the given voice."""
    valid_voice_ids = {v.voice_id: v.model for v in VOICE_POOL}
    if voice_id not in valid_voice_ids:
        raise HTTPException(status_code=404, detail="Voice not found in pool")

    try:
        preview_path = generate_voice_preview(voice_id, model=valid_voice_ids[voice_id])
    except ElevenLabsError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to generate voice preview: {exc}",
        ) from exc

    return FileResponse(preview_path, media_type="audio/mpeg")
