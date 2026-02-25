import json
import logging
import re
from urllib.parse import urlparse, urlunparse
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.story import Story, PlaybackState, StoryView, StoryFolder, StoryFolderMembership
from app.schemas.story import (
    StorySubmitRequest,
    ManualStorySubmitRequest,
    StoryResponse,
    StoryListResponse,
    PlaybackStateRequest,
    PlaybackStateResponse,
    DuplicateCheckResponse,
    FolderCreateRequest,
    FolderResponse,
    FolderAddStoryRequest,
)
from app.services.reddit import fetch_multi_part_story, fetch_story_text, fetch_post_metadata, find_series_parts
from app.services.hashing import hash_content
from app.services.text_cleaner import clean_for_narration
from app.models.story import User
from app.deps import get_current_user, get_optional_user
from app.rate_limit import rate_limit

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Reddit URL validation ─────────────────────────────────────────

_ALLOWED_REDDIT_HOSTS = frozenset({"reddit.com", "www.reddit.com", "old.reddit.com"})
_NOSLEEP_PATH_RE = re.compile(r"^/r/nosleep/comments/[a-zA-Z0-9_]+", re.IGNORECASE)


def _validate_and_normalize_reddit_url(url: str) -> str:
    """Validate that *url* points to a r/nosleep post and return a normalized form.

    Raises HTTPException(400) for any URL that:
    - is not http/https
    - does not originate from reddit.com / www.reddit.com / old.reddit.com
    - does not match the /r/nosleep/comments/<id> path pattern

    Query strings and fragments are stripped so that share-link variants
    (e.g. ``?utm_source=…``) do not create duplicate entries or cause
    ``_reddit_get`` to append ``.json`` to a non-path segment.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid URL")

    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Invalid URL: scheme must be http or https")

    if parsed.netloc.lower() not in _ALLOWED_REDDIT_HOSTS:
        raise HTTPException(status_code=400, detail="Invalid URL: host must be reddit.com or www.reddit.com")

    if not _NOSLEEP_PATH_RE.match(parsed.path):
        raise HTTPException(status_code=400, detail="Invalid URL: must link to a r/nosleep post (/r/nosleep/comments/…)")

    # Normalize: drop query string and fragment to prevent duplicates and
    # to avoid breaking the Reddit .json fetch helper.
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


@router.post("/submit", response_model=StoryResponse)
def submit_story(req: StorySubmitRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Fetch a story from a NoSleep URL and store it.

    If the story already exists (by URL or content hash), returns the existing
    record so the user is seamlessly directed to the story detail page.
    """

    # Validate and normalize the Reddit URL (prevents SSRF; strips query/fragment)
    reddit_url = _validate_and_normalize_reddit_url(req.reddit_url)

    # Return existing story if this URL was already submitted
    existing = db.query(Story).filter(Story.reddit_url == reddit_url).first()
    if existing:
        return existing

    # Fetch post metadata (title, author, etc.) via Reddit .json endpoint
    try:
        metadata = fetch_post_metadata(reddit_url)
        title = metadata["title"]
        author = metadata.get("author", "")
    except Exception as e:
        logger.error(f"Failed to fetch Reddit submission: {e}")
        raise HTTPException(status_code=400, detail=f"Could not fetch Reddit post: {e}")

    # Fetch full text (multi-part aware)
    try:
        text = fetch_multi_part_story(reddit_url)
    except Exception as e:
        logger.error(f"Failed to fetch story text: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to extract story text: {e}")

    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Story has no text content")

    # Count parts by separator
    parts = text.split("\n\n---\n\n")
    part_count = len(parts)

    # Return existing story if content matches (same story, different URL)
    content_digest = hash_content(text)
    duplicate = db.query(Story).filter(Story.content_hash == content_digest).first()
    if duplicate:
        return duplicate

    narration = clean_for_narration(text)

    # Discover series parts from author's page (best-effort)
    series_parts = []
    if author:
        try:
            series_parts = find_series_parts(author, title)
        except Exception:
            pass

    story = Story(
        title=title,
        author=author or None,
        reddit_url=reddit_url,
        text_content=text,
        narration_text=narration,
        content_hash=content_digest,
        part_count=part_count,
        series_json=json.dumps(series_parts) if series_parts else None,
    )
    db.add(story)
    db.commit()
    db.refresh(story)

    return story


@router.post("/submit-manual", response_model=StoryResponse)
def submit_story_manual(req: ManualStorySubmitRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Submit a story via manual entry.

    All fields are optional:
    - If a reddit_url is provided, the title and text will be fetched from
      Reddit (any user-supplied title/text is ignored in that case).
    - If no URL is given, at least a title and text_content must be provided.
    """

    title = (req.title or "").strip()
    text = (req.text_content or "").strip()
    url = (req.reddit_url or "").strip() or None
    author = None

    # Validate and normalize the Reddit URL when provided (prevents SSRF; strips query/fragment)
    if url:
        url = _validate_and_normalize_reddit_url(url)

    # Check for duplicate by URL first
    if url:
        existing = db.query(Story).filter(Story.reddit_url == url).first()
        if existing:
            return existing

    # If a URL was provided, fetch any missing title/text from Reddit
    if url and (not title or not text):
        try:
            metadata = fetch_post_metadata(url)
            if not title:
                title = metadata["title"]
            if author is None:
                author = metadata.get("author", "")
        except Exception as e:
            logger.error(f"Failed to fetch Reddit submission: {e}")
            raise HTTPException(status_code=400, detail=f"Could not fetch Reddit post: {e}")

        if not text:
            try:
                text = fetch_multi_part_story(url)
            except Exception as e:
                logger.error(f"Failed to fetch story text: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to extract story text: {e}")

    if not text:
        raise HTTPException(status_code=400, detail="Story text cannot be empty")
    if not title:
        raise HTTPException(status_code=400, detail="Story title cannot be empty")

    # Check for duplicate by content hash
    content_digest = hash_content(text)
    duplicate = db.query(Story).filter(Story.content_hash == content_digest).first()
    if duplicate:
        return duplicate

    # Count parts by separator
    parts = text.split("\n\n---\n\n")
    part_count = len(parts)

    narration = clean_for_narration(text)

    # Discover series parts from author's page (best-effort)
    series_parts = []
    if author:
        try:
            series_parts = find_series_parts(author, title)
        except Exception:
            pass

    story = Story(
        title=title,
        author=author or None,
        reddit_url=url,
        text_content=text,
        narration_text=narration,
        content_hash=content_digest,
        part_count=part_count,
        series_json=json.dumps(series_parts) if series_parts else None,
    )
    db.add(story)
    db.commit()
    db.refresh(story)

    return story


@router.get("/", response_model=list[StoryListResponse])
def list_stories(skip: int = 0, limit: int = 25, db: Session = Depends(get_db)):
    """List all stored stories with pagination."""
    stories = db.query(Story).order_by(Story.created_at.desc()).offset(skip).limit(limit).all()
    return [
        StoryListResponse(
            id=s.id,
            title=s.title,
            author=s.author,
            reddit_url=s.reddit_url,
            has_audio=s.audio_file_path is not None,
            has_script=s.script_json is not None,
            part_count=s.part_count,
            created_at=s.created_at,
        )
        for s in stories
    ]


@router.get("/top-nosleep")
def top_nosleep_posts(timeframe: str = "alltime", limit: int = 50, db: Session = Depends(get_db)):
    """Fetch top posts from r/nosleep for the story browser.

    Returns a list of posts with title, URL, score, author, gilding, and flair.
    Already-submitted stories are flagged so the frontend can indicate them.
    Uses a configurable cache TTL (default 1 week) from app settings.
    """
    from app.services.reddit import fetch_top_posts
    from app.models.app_setting import get_setting

    cache_ttl = int(get_setting(db, "reddit_cache_ttl", "604800"))

    try:
        posts = fetch_top_posts(timeframe=timeframe, limit=limit, cache_ttl=cache_ttl)
    except Exception as e:
        logger.warning("Failed to fetch top NoSleep posts: %s", e)
        raise HTTPException(
            status_code=502,
            detail=f"Reddit is currently unreachable: {e}"
        )

    # Check which URLs are already in the database
    existing_urls = {
        row[0] for row in db.query(Story.reddit_url).all()
    }

    for post in posts:
        post["already_submitted"] = post["url"] in existing_urls

    return posts


@router.get("/fetch-preview")
def fetch_preview(reddit_url: str, _rl=Depends(rate_limit(30, 60)), user: User = Depends(get_current_user)):
    """Fetch title and first-part text from a Reddit URL without creating a story.

    Used by the manual entry pop-out to auto-populate fields once
    a valid URL is entered.  Only the first post's text is fetched
    (not the full multi-part chain) to keep preview requests cheap.
    Rate-limited to 30 requests per minute per user.
    """
    if not reddit_url or not reddit_url.strip():
        raise HTTPException(status_code=400, detail="URL is required")

    # Validate and normalize (prevents SSRF; strips query/fragment)
    reddit_url = _validate_and_normalize_reddit_url(reddit_url.strip())

    try:
        metadata = fetch_post_metadata(reddit_url)
        title = metadata.get("title", "")
        author = metadata.get("author", "")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not fetch Reddit post: {e}")

    try:
        text = fetch_story_text(reddit_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract story text: {e}")

    return {"title": title, "author": author, "text": text or ""}


@router.get("/check-duplicate/", response_model=DuplicateCheckResponse)
def check_duplicate(reddit_url: str, db: Session = Depends(get_db)):
    """Pre-check if a URL or its content already exists before full submission."""
    existing = db.query(Story).filter(Story.reddit_url == reddit_url).first()
    if existing:
        return DuplicateCheckResponse(
            is_duplicate=True,
            existing_story_id=existing.id,
            message=f"URL already submitted as story #{existing.id}: '{existing.title}'"
        )
    return DuplicateCheckResponse(
        is_duplicate=False,
        existing_story_id=None,
        message="No duplicate found"
    )


# ── Story view tracking & hide ───────────────────────────────────

@router.post("/{story_id}/hide")
def hide_story_from_home(story_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Hide a story from the user's Recently Viewed list on the home page."""
    view = db.query(StoryView).filter(
        StoryView.user_id == user.id,
        StoryView.story_id == story_id,
    ).first()
    if view:
        view.hidden = True
        db.commit()
    return {"ok": True}


@router.post("/{story_id}/unhide")
def unhide_story(story_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Restore a hidden story back to the Recently Viewed list."""
    view = db.query(StoryView).filter(
        StoryView.user_id == user.id,
        StoryView.story_id == story_id,
    ).first()
    if view:
        view.hidden = False
        db.commit()
    return {"ok": True}


# ── Folder management ────────────────────────────────────────────

@router.get("/folders/list", response_model=list[FolderResponse])
def list_folders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """List all folders for the current user."""
    rows = (
        db.query(StoryFolder, func.count(StoryFolderMembership.story_id).label("story_count"))
        .outerjoin(StoryFolderMembership, StoryFolderMembership.folder_id == StoryFolder.id)
        .filter(StoryFolder.user_id == user.id)
        .group_by(StoryFolder.id)
        .order_by(StoryFolder.name)
        .all()
    )
    return [
        FolderResponse(id=f.id, name=f.name, story_count=count, created_at=f.created_at)
        for f, count in rows
    ]


@router.post("/folders/create", response_model=FolderResponse)
def create_folder(req: FolderCreateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create a new folder for the current user."""
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Folder name cannot be empty")
    if len(name) > 60:
        raise HTTPException(status_code=400, detail="Folder name cannot be longer than 60 characters")
    existing = db.query(StoryFolder).filter(
        StoryFolder.user_id == user.id,
        StoryFolder.name == name,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="A folder with this name already exists")
    folder = StoryFolder(user_id=user.id, name=name)
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return FolderResponse(id=folder.id, name=folder.name, story_count=0, created_at=folder.created_at)


@router.delete("/folders/{folder_id}")
def delete_folder(folder_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete a folder and all its memberships."""
    folder = db.query(StoryFolder).filter(
        StoryFolder.id == folder_id,
        StoryFolder.user_id == user.id,
    ).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    db.query(StoryFolderMembership).filter(StoryFolderMembership.folder_id == folder_id).delete()
    db.delete(folder)
    db.commit()
    return {"ok": True}


@router.post("/folders/{folder_id}/add")
def add_story_to_folder(folder_id: int, req: FolderAddStoryRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Add a story to a folder."""
    folder = db.query(StoryFolder).filter(
        StoryFolder.id == folder_id,
        StoryFolder.user_id == user.id,
    ).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    story = db.query(Story).filter(Story.id == req.story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    existing = db.query(StoryFolderMembership).filter(
        StoryFolderMembership.folder_id == folder_id,
        StoryFolderMembership.story_id == req.story_id,
    ).first()
    if existing:
        return {"ok": True, "message": "Story already in folder"}
    membership = StoryFolderMembership(folder_id=folder_id, story_id=req.story_id)
    db.add(membership)
    db.commit()
    return {"ok": True}


@router.delete("/folders/{folder_id}/stories/{story_id}")
def remove_story_from_folder(folder_id: int, story_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Remove a story from a folder."""
    folder = db.query(StoryFolder).filter(
        StoryFolder.id == folder_id,
        StoryFolder.user_id == user.id,
    ).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    db.query(StoryFolderMembership).filter(
        StoryFolderMembership.folder_id == folder_id,
        StoryFolderMembership.story_id == story_id,
    ).delete()
    db.commit()
    return {"ok": True}


@router.get("/{story_id}/series-parts")
def get_series_parts(story_id: int, db: Session = Depends(get_db)):
    """Return discovered series parts for a story.

    Checks the cached series_json first. If not available and the story
    has an author, attempts discovery from the author's Reddit page.
    """
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    # Return cached series parts if available
    if story.series_json:
        return json.loads(story.series_json)

    # Attempt discovery if we have an author
    if story.author and story.title:
        try:
            parts = find_series_parts(story.author, story.title)
            if parts:
                story.series_json = json.dumps(parts)
                db.commit()
            return parts
        except Exception:
            pass

    return []


@router.get("/{story_id}", response_model=StoryResponse)
def get_story(story_id: int, db: Session = Depends(get_db)):
    """Get a single story by ID."""
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    return story


@router.post("/playback", response_model=PlaybackStateResponse)
def save_playback_position(req: PlaybackStateRequest, user: User | None = Depends(get_optional_user), db: Session = Depends(get_db)):
    """Save the current playback position for a story so it can be resumed later.

    Requires authentication so each user gets their own playback position.
    Anonymous requests are silently ignored (returns zero position).
    """
    if not user:
        return PlaybackStateResponse(story_id=req.story_id, position_seconds=0.0)

    story = db.query(Story).filter(Story.id == req.story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    state = db.query(PlaybackState).filter(
        PlaybackState.user_id == user.id,
        PlaybackState.story_id == req.story_id,
    ).first()
    if state:
        state.position_seconds = req.position_seconds
    else:
        state = PlaybackState(user_id=user.id, story_id=req.story_id, position_seconds=req.position_seconds)
        db.add(state)

    db.commit()
    db.refresh(state)

    return PlaybackStateResponse(
        story_id=state.story_id,
        user_id=state.user_id,
        position_seconds=state.position_seconds,
        updated_at=state.updated_at,
    )


@router.get("/playback/{story_id}", response_model=PlaybackStateResponse)
def get_playback_position(story_id: int, user: User | None = Depends(get_optional_user), db: Session = Depends(get_db)):
    """Get the saved playback position for a story to resume listening.

    Returns the position for the authenticated user, or 0.0 for anonymous users.
    """
    if not user:
        return PlaybackStateResponse(story_id=story_id, position_seconds=0.0)

    state = db.query(PlaybackState).filter(
        PlaybackState.user_id == user.id,
        PlaybackState.story_id == story_id,
    ).first()
    if not state:
        return PlaybackStateResponse(story_id=story_id, position_seconds=0.0)
    return PlaybackStateResponse(
        story_id=state.story_id,
        user_id=state.user_id,
        position_seconds=state.position_seconds,
        updated_at=state.updated_at,
    )
