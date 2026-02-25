import json
import os
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy.sql import func as sql_func
from app.database import get_db
from app.models.story import Story, PlaybackState, User, StoryView, StoryFolder, StoryFolderMembership
from app.schemas.narration import NarrationScript
from app.deps import get_optional_user
from app.services.voice_pool import VOICE_POOL

logger = logging.getLogger(__name__)

router = APIRouter()


def _record_story_view(db: Session, user: User | None, story_id: int):
    """Record or refresh a story view for the current user."""
    if not user:
        return
    view = db.query(StoryView).filter(
        StoryView.user_id == user.id,
        StoryView.story_id == story_id,
    ).first()
    if view:
        view.viewed_at = datetime.now(timezone.utc)
        if view.hidden:
            view.hidden = False
    else:
        view = StoryView(user_id=user.id, story_id=story_id)
        db.add(view)
    db.commit()

templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
)


@router.get("/", response_class=HTMLResponse)
def story_list_page(request: Request, db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)):
    """Serve the story browser page.

    Logged-in users see their recently viewed stories (unhidden).
    Anonymous users see all stories.
    """
    folders = []
    if user:
        # Recently viewed stories, excluding hidden ones, newest view first
        viewed_rows = (
            db.query(StoryView, Story)
            .join(Story, Story.id == StoryView.story_id)
            .filter(StoryView.user_id == user.id, StoryView.hidden.is_(False))
            .order_by(StoryView.viewed_at.desc())
            .limit(50)
            .all()
        )
        stories = [row[1] for row in viewed_rows]
        folders = db.query(StoryFolder).filter(
            StoryFolder.user_id == user.id
        ).order_by(StoryFolder.name).all()
    else:
        stories = db.query(Story).order_by(Story.created_at.desc()).all()

    return templates.TemplateResponse("story_list.html", {
        "request": request,
        "stories": stories,
        "user": user,
        "folders": folders,
        "is_recently_viewed": user is not None,
    })


@router.get("/folder/{folder_id}", response_class=HTMLResponse)
def folder_page(request: Request, folder_id: int, db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)):
    """Serve a page showing all stories in a specific folder."""
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    folder = db.query(StoryFolder).filter(
        StoryFolder.id == folder_id,
        StoryFolder.user_id == user.id,
    ).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    memberships = (
        db.query(Story)
        .join(StoryFolderMembership, StoryFolderMembership.story_id == Story.id)
        .filter(StoryFolderMembership.folder_id == folder_id)
        .order_by(StoryFolderMembership.added_at.desc())
        .all()
    )
    folders = db.query(StoryFolder).filter(
        StoryFolder.user_id == user.id
    ).order_by(StoryFolder.name).all()
    return templates.TemplateResponse("folder.html", {
        "request": request,
        "folder": folder,
        "stories": memberships,
        "folders": folders,
        "user": user,
    })


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    """Serve the login/register page."""
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/submit", response_class=HTMLResponse)
def submit_page(request: Request, user: User | None = Depends(get_optional_user)):
    """Serve the story submission page with URL input and Best of All Time browser."""
    return templates.TemplateResponse("submit.html", {"request": request, "user": user})


@router.get("/story/{story_id}", response_class=HTMLResponse)
def story_detail_page(request: Request, story_id: int, db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)):
    """Serve the story detail page with teaser, pipeline controls, and playback info."""
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    _record_story_view(db, user, story_id)

    # Build a 2-4 sentence teaser from the narration text
    teaser = ""
    source_text = story.narration_text or story.text_content or ""
    if source_text:
        import re
        sentences = re.split(r'(?<=[.!?])\s+', source_text.strip())
        teaser = " ".join(sentences[:3])
        if len(teaser) > 400:
            teaser = teaser[:397] + "..."

    # Estimate word count and listening duration
    word_count = len(source_text.split()) if source_text else 0
    # ~150 words per minute for dramatic narration
    est_minutes = round(word_count / 150) if word_count else 0

    # Parse script stats if available
    segment_count = 0
    voice_count = 0
    sfx_count = 0
    if story.script_json:
        try:
            script = NarrationScript(**json.loads(story.script_json))
            segment_count = len(script.segments)
            voice_count = len(script.voice_segments())
            sfx_count = len(script.sfx_segments())
        except Exception:
            pass

    # Get playback position if the user has started listening
    playback = None
    if user:
        playback = db.query(PlaybackState).filter(
            PlaybackState.user_id == user.id,
            PlaybackState.story_id == story_id,
        ).first()
    resume_seconds = playback.position_seconds if playback else 0.0

    return templates.TemplateResponse("story_detail.html", {
        "request": request,
        "story": story,
        "teaser": teaser,
        "word_count": word_count,
        "est_minutes": est_minutes,
        "segment_count": segment_count,
        "voice_count": voice_count,
        "sfx_count": sfx_count,
        "resume_seconds": resume_seconds,
        "user": user,
    })


@router.get("/story/{story_id}/edit-script", response_class=HTMLResponse)
def script_editor_page(request: Request, story_id: int, db: Session = Depends(get_db)):
    """Serve the script editor page for a story."""
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    if not story.script_json:
        raise HTTPException(status_code=404, detail="No script generated for this story yet")

    voice_pool_json = json.dumps([
        {"voice_id": v.voice_id, "name": v.name, "gender": v.gender,
         "age": v.age, "archetypes": v.archetypes}
        for v in VOICE_POOL
    ])

    return templates.TemplateResponse("script_editor.html", {
        "request": request,
        "story": story,
        "script_json": story.script_json,
        "voice_pool_json": voice_pool_json,
    })


@router.get("/listen/{story_id}", response_class=HTMLResponse)
def player_page(request: Request, story_id: int, db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)):
    """Serve the audio player page for a specific story."""
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    if not story.audio_file_path:
        raise HTTPException(status_code=404, detail="No audio generated for this story yet")

    _record_story_view(db, user, story_id)

    # Get saved playback position for the current user
    state = None
    if user:
        state = db.query(PlaybackState).filter(
            PlaybackState.user_id == user.id,
            PlaybackState.story_id == story_id,
        ).first()
    resume_position = state.position_seconds if state else 0.0

    return templates.TemplateResponse("player.html", {
        "request": request,
        "story": story,
        "resume_position": resume_position,
    })


@router.get("/stream/{story_id}")
def stream_audio(request: Request, story_id: int, db: Session = Depends(get_db)):
    """Stream the audio file for a story with HTTP Range request support.

    Range requests are essential for:
    - Mobile browsers seeking within audio
    - Lock-screen playback on Android (Samsung Internet, Chrome)
    - Resuming from a saved position without downloading the whole file
    """
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story or not story.audio_file_path:
        raise HTTPException(status_code=404, detail="Audio not found")

    file_path = story.audio_file_path
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Audio file missing from disk")

    file_size = os.path.getsize(file_path)
    range_header = request.headers.get("range")

    if range_header:
        # Parse Range: bytes=start-end
        range_spec = range_header.replace("bytes=", "").strip()
        parts = range_spec.split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if len(parts) > 1 and parts[1] else file_size - 1

        # Clamp to file bounds
        start = max(0, min(start, file_size - 1))
        end = max(start, min(end, file_size - 1))
        content_length = end - start + 1

        def iter_range():
            with open(file_path, "rb") as f:
                f.seek(start)
                remaining = content_length
                while remaining > 0:
                    chunk_size = min(8192, remaining)
                    data = f.read(chunk_size)
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        return StreamingResponse(
            iter_range(),
            status_code=206,
            media_type="audio/mpeg",
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(content_length),
                "Content-Type": "audio/mpeg",
                "Cache-Control": "public, max-age=86400",
            },
        )

    # No range header — serve the full file
    return FileResponse(
        file_path,
        media_type="audio/mpeg",
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
            "Cache-Control": "public, max-age=86400",
        },
    )


@router.get("/download/{story_id}")
def download_audio(story_id: int, db: Session = Depends(get_db)):
    """Download the audio file for a story."""
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story or not story.audio_file_path:
        raise HTTPException(status_code=404, detail="Audio not found")

    file_path = story.audio_file_path
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Audio file missing from disk")

    safe_title = "".join(c for c in story.title if c.isalnum() or c in " -_").strip()
    filename = f"{safe_title}.mp3"

    return FileResponse(
        file_path,
        media_type="audio/mpeg",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
