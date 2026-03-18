"""Stories API endpoints for Django Ninja.

Ported from app/routers/stories.py — story submission, listing, folders, playback.
"""

import json
import logging
import re
from urllib.parse import urlparse, urlunparse

from django.db import IntegrityError
from django.db.models import Count, Exists, OuterRef
from ninja import Router
from ninja.errors import HttpError

from apps.accounts.auth import get_current_user, get_optional_user
from apps.common.rate_limit import check_rate_limit
from apps.player.models import PlaybackState
from apps.stories.models import (
    AppSetting,
    Story,
    StoryFolder,
    StoryFolderMembership,
    StoryView,
    NarrationScript,
)
from schemas.story import (
    DuplicateCheckResponse,
    FolderAddStoryRequest,
    FolderCreateRequest,
    FolderResponse,
    ManualStorySubmitRequest,
    PlaybackStateRequest,
    PlaybackStateResponse,
    StoryListResponse,
    StoryResponse,
    StorySubmitRequest,
)
from services.hashing import hash_content
from services.reddit import fetch_post_metadata, fetch_story_text, find_series_parts
from services.text_cleaner import clean_for_narration

logger = logging.getLogger(__name__)

router = Router()

# ── Reddit URL validation ─────────────────────────────────────────

_ALLOWED_REDDIT_HOSTS = frozenset({"reddit.com", "www.reddit.com", "old.reddit.com"})
_NOSLEEP_PATH_RE = re.compile(r"^/r/nosleep/comments/[a-zA-Z0-9_]+", re.IGNORECASE)


def _validate_and_normalize_reddit_url(url: str) -> str:
    """Validate that *url* points to a r/nosleep post and return a normalized form."""
    try:
        parsed = urlparse(url)
    except Exception:
        raise HttpError(400, "Invalid URL")

    if parsed.scheme not in ("http", "https"):
        raise HttpError(400, "Invalid URL: scheme must be http or https")

    if parsed.netloc.lower() not in _ALLOWED_REDDIT_HOSTS:
        raise HttpError(400, "Invalid URL: host must be reddit.com or www.reddit.com")

    if not _NOSLEEP_PATH_RE.match(parsed.path):
        raise HttpError(400, "Invalid URL: must link to a r/nosleep post (/r/nosleep/comments/…)")

    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def _canonical_url_key(url: str) -> tuple[str, str]:
    """Return (netloc_without_www, path_without_trailing_slash) for URL dedup."""
    parsed = urlparse(url)
    netloc = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/")
    return (netloc, path)


def _story_to_response(story: Story) -> dict:
    """Convert a Django Story model to a StoryResponse-compatible dict."""
    return {
        "id": story.id,
        "title": story.title,
        "author": story.author or None,
        "reddit_url": story.reddit_url or None,
        "narration_text": story.narration_text or None,
        "content_hash": story.content_hash,
        "audio_file_path": story.audio_file_path or None,
        "part_count": story.part_count,
        "created_at": story.created_at,
    }


def _auto_submit_series_parts(
    series_parts: list[dict],
    submitted_url: str,
    author: str | None,
    series_json: list,
    part_count: int,
) -> None:
    """Create Story records for all other parts in a series (best-effort)."""
    submitted_key = _canonical_url_key(submitted_url)

    candidate_urls = set()
    for part in series_parts:
        raw = (part.get("url") or "").strip()
        if not raw:
            continue
        base = raw.rstrip("/")
        candidate_urls.add(base)
        candidate_urls.add(base + "/")
        try:
            p = urlparse(raw)
            alt_netloc = p.netloc.lower()
            alt_netloc = alt_netloc[4:] if alt_netloc.startswith("www.") else "www." + alt_netloc
            alt = p._replace(netloc=alt_netloc).geturl().rstrip("/")
            candidate_urls.add(alt)
            candidate_urls.add(alt + "/")
        except Exception:
            pass

    existing_keys: set[tuple[str, str]] = set()
    if candidate_urls:
        for row in Story.objects.filter(reddit_url__in=candidate_urls).values_list("reddit_url", flat=True):
            if row:
                existing_keys.add(_canonical_url_key(row))

    stories_to_create = []
    for part in series_parts:
        part_url = (part.get("url") or "").strip()
        if not part_url:
            continue
        if _canonical_url_key(part_url) == submitted_key:
            continue

        part_key = _canonical_url_key(part_url)
        if part_key in existing_keys:
            continue

        # Check with URL variants
        parsed = urlparse(part_url)
        netlocs = {parsed.netloc}
        if parsed.netloc.lower().startswith("www."):
            netlocs.add(parsed.netloc[4:])
        elif parsed.netloc:
            netlocs.add("www." + parsed.netloc)
        paths = {parsed.path}
        if parsed.path:
            paths.add(parsed.path.rstrip("/"))
            if not parsed.path.endswith("/"):
                paths.add(parsed.path.rstrip("/") + "/")
        url_variants = set()
        for netloc in netlocs:
            for path in paths:
                url_variants.add(urlunparse((parsed.scheme, netloc, path, parsed.params, parsed.query, parsed.fragment)))
        if Story.objects.filter(reddit_url__in=url_variants).exists():
            continue

        try:
            part_text = fetch_story_text(part_url)
        except Exception:
            logger.debug("Failed to fetch series part %s", part_url)
            continue

        if not part_text or not part_text.strip():
            continue

        content_digest = hash_content(part_text)
        if Story.objects.filter(content_hash=content_digest).exists():
            existing_keys.add(part_key)
            continue

        narration = clean_for_narration(part_text)
        story = Story(
            title=part.get("title", "Unknown"),
            author=author or "",
            reddit_url=part_url,
            text_content=part_text,
            narration_text=narration,
            content_hash=content_digest,
            part_count=part_count,
            series_json=series_parts,
        )
        stories_to_create.append(story)
        existing_keys.add(part_key)

    if stories_to_create:
        try:
            Story.objects.bulk_create(stories_to_create)
        except Exception:
            logger.warning("Failed to auto-submit some series parts")


# ── Story submission ─────────────────────────────────────────────


@router.post("/submit", response=StoryResponse)
def submit_story(request, payload: StorySubmitRequest):
    """Fetch a story from a NoSleep URL and store it."""
    get_current_user(request)

    reddit_url = _validate_and_normalize_reddit_url(payload.reddit_url)

    existing = Story.objects.filter(reddit_url=reddit_url).first()
    if existing:
        return _story_to_response(existing)

    try:
        metadata = fetch_post_metadata(reddit_url)
        title = metadata["title"]
        author = metadata.get("author", "")
    except Exception as e:
        logger.error("Failed to fetch Reddit submission: %s", e)
        raise HttpError(400, f"Could not fetch Reddit post: {e}")

    try:
        text = fetch_story_text(reddit_url)
    except Exception as e:
        logger.error("Failed to fetch story text: %s", e)
        raise HttpError(500, f"Failed to extract story text: {e}")

    if not text or not text.strip():
        raise HttpError(400, "Story has no text content")

    content_digest = hash_content(text)
    duplicate = Story.objects.filter(content_hash=content_digest).first()
    if duplicate:
        return _story_to_response(duplicate)

    narration = clean_for_narration(text)

    series_parts = []
    if author:
        try:
            series_parts = find_series_parts(author, title)
        except Exception:
            pass

    part_count = len(series_parts) if series_parts else 1
    series_json = series_parts if series_parts else None

    story = Story.objects.create(
        title=title,
        author=author or "",
        reddit_url=reddit_url,
        text_content=text,
        narration_text=narration,
        content_hash=content_digest,
        part_count=part_count,
        series_json=series_json,
    )

    if series_parts:
        _auto_submit_series_parts(series_parts, reddit_url, author, series_parts, part_count)

    return _story_to_response(story)


@router.post("/submit-manual", response=StoryResponse)
def submit_story_manual(request, payload: ManualStorySubmitRequest):
    """Submit a story via manual entry."""
    get_current_user(request)

    title = (payload.title or "").strip()
    text = (payload.text_content or "").strip()
    url = (payload.reddit_url or "").strip() or None
    author = (payload.author or "").strip() or None

    if url:
        url = _validate_and_normalize_reddit_url(url)

    if url:
        existing = Story.objects.filter(reddit_url=url).first()
        if existing:
            return _story_to_response(existing)

    if url and (not title or not text):
        try:
            metadata = fetch_post_metadata(url)
            if not title:
                title = metadata["title"]
            if author is None:
                author = metadata.get("author", "")
        except Exception as e:
            logger.error("Failed to fetch Reddit submission: %s", e)
            raise HttpError(400, f"Could not fetch Reddit post: {e}")

        if not text:
            try:
                text = fetch_story_text(url)
            except Exception as e:
                logger.error("Failed to fetch story text: %s", e)
                raise HttpError(500, f"Failed to extract story text: {e}")

    if not text:
        raise HttpError(400, "Story text cannot be empty")
    if not title:
        raise HttpError(400, "Story title cannot be empty")

    content_digest = hash_content(text)
    duplicate = Story.objects.filter(content_hash=content_digest).first()
    if duplicate:
        return _story_to_response(duplicate)

    narration = clean_for_narration(text)

    series_parts = []
    if author:
        try:
            series_parts = find_series_parts(author, title)
        except Exception:
            pass

    part_count = len(series_parts) if series_parts else 1
    series_json = series_parts if series_parts else None

    story = Story.objects.create(
        title=title,
        author=author or "",
        reddit_url=url,
        text_content=text,
        narration_text=narration,
        content_hash=content_digest,
        part_count=part_count,
        series_json=series_json,
    )

    if series_parts and url:
        _auto_submit_series_parts(series_parts, url, author, series_parts, part_count)

    return _story_to_response(story)


# ── Story listing ────────────────────────────────────────────────


@router.get("/", response=list[StoryListResponse])
def list_stories(request, skip: int = 0, limit: int = 25):
    """List all stored stories with pagination."""
    stories = Story.objects.order_by("-created_at")[skip:skip + limit]
    return [
        {
            "id": s.id,
            "title": s.title,
            "author": s.author or None,
            "reddit_url": s.reddit_url or None,
            "has_audio": bool(s.audio_file_path),
            "has_script": hasattr(s, "script") and s.script is not None,
            "part_count": s.part_count,
            "created_at": s.created_at,
        }
        for s in stories
    ]


@router.get("/top-nosleep")
def top_nosleep_posts(request, timeframe: str = "alltime", limit: int = 50):
    """Fetch top posts from r/nosleep for the story browser."""
    from services.reddit import fetch_top_posts

    cache_ttl = int(AppSetting.get("reddit_cache_ttl", "604800"))

    try:
        posts = fetch_top_posts(timeframe=timeframe, limit=limit, cache_ttl=cache_ttl)
    except Exception as e:
        logger.warning("Failed to fetch top NoSleep posts: %s", e)
        raise HttpError(502, f"Reddit is currently unreachable: {e}")

    existing_urls = set(
        Story.objects.values_list("reddit_url", flat=True)
    )

    for post in posts:
        post["already_submitted"] = post["url"] in existing_urls

    return posts


@router.get("/fetch-preview")
def fetch_preview(request, reddit_url: str):
    """Fetch title and first-part text from a Reddit URL without creating a story."""
    user = get_current_user(request)
    check_rate_limit(user.id, 30, 60)

    if not reddit_url or not reddit_url.strip():
        raise HttpError(400, "URL is required")

    reddit_url = _validate_and_normalize_reddit_url(reddit_url.strip())

    try:
        metadata = fetch_post_metadata(reddit_url)
        title = metadata.get("title", "")
        author = metadata.get("author", "")
    except Exception as e:
        raise HttpError(400, f"Could not fetch Reddit post: {e}")

    try:
        text = fetch_story_text(reddit_url)
    except Exception as e:
        raise HttpError(500, f"Failed to extract story text: {e}")

    return {"title": title, "author": author, "text": text or ""}


@router.get("/check-duplicate/", response=DuplicateCheckResponse)
def check_duplicate(request, reddit_url: str):
    """Pre-check if a URL or its content already exists before full submission."""
    existing = Story.objects.filter(reddit_url=reddit_url).first()
    if existing:
        return {
            "is_duplicate": True,
            "existing_story_id": existing.id,
            "message": f"URL already submitted as story #{existing.id}: '{existing.title}'",
        }
    return {
        "is_duplicate": False,
        "existing_story_id": None,
        "message": "No duplicate found",
    }


# ── Story view tracking & hide ───────────────────────────────────


@router.post("/{story_id}/hide")
def hide_story_from_home(request, story_id: int):
    """Hide a story from the user's Recently Viewed list."""
    user = get_current_user(request)
    StoryView.objects.filter(user=user, story_id=story_id).update(hidden=True)
    return {"ok": True}


@router.post("/{story_id}/unhide")
def unhide_story(request, story_id: int):
    """Restore a hidden story back to the Recently Viewed list."""
    user = get_current_user(request)
    StoryView.objects.filter(user=user, story_id=story_id).update(hidden=False)
    return {"ok": True}


# ── Folder management ────────────────────────────────────────────


@router.get("/folders/list", response=list[FolderResponse])
def list_folders(request):
    """List all folders for the current user."""
    user = get_current_user(request)
    folders = (
        StoryFolder.objects.filter(user=user)
        .annotate(story_count=Count("storyfoldermembership"))
        .order_by("name")
    )
    return [
        {
            "id": f.id,
            "name": f.name,
            "story_count": f.story_count,
            "created_at": f.created_at,
        }
        for f in folders
    ]


@router.post("/folders/create", response=FolderResponse)
def create_folder(request, payload: FolderCreateRequest):
    """Create a new folder for the current user."""
    user = get_current_user(request)
    name = payload.name
    if not name:
        raise HttpError(400, "Folder name cannot be empty")
    if len(name) > 60:
        raise HttpError(400, "Folder name cannot be longer than 60 characters")

    if StoryFolder.objects.filter(user=user, name__iexact=name).exists():
        raise HttpError(409, "A folder with this name already exists")

    try:
        folder = StoryFolder.objects.create(user=user, name=name)
    except IntegrityError:
        raise HttpError(409, "A folder with this name already exists")

    return {"id": folder.id, "name": folder.name, "story_count": 0, "created_at": folder.created_at}


@router.delete("/folders/{folder_id}")
def delete_folder(request, folder_id: int):
    """Delete a folder and all its memberships."""
    user = get_current_user(request)
    folder = StoryFolder.objects.filter(id=folder_id, user=user).first()
    if not folder:
        raise HttpError(404, "Folder not found")
    StoryFolderMembership.objects.filter(folder=folder).delete()
    folder.delete()
    return {"ok": True}


@router.get("/folders/{folder_id}/stories", response=list[StoryListResponse])
def list_folder_stories(request, folder_id: int):
    """List all stories in a specific folder."""
    user = get_current_user(request)
    folder = StoryFolder.objects.filter(id=folder_id, user=user).first()
    if not folder:
        raise HttpError(404, "Folder not found")
    story_ids = StoryFolderMembership.objects.filter(folder=folder).values_list(
        "story_id", flat=True
    )
    stories = (
        Story.objects.filter(id__in=story_ids)
        .annotate(
            has_script=Exists(
                NarrationScript.objects.filter(story_id=OuterRef("pk"))
            )
        )
        .order_by("-created_at")
    )
    return [
        {
            "id": s.id,
            "title": s.title,
            "author": s.author or None,
            "reddit_url": s.reddit_url or None,
            "has_audio": bool(s.audio_file_path),
            "has_script": s.has_script,
            "part_count": s.part_count,
            "created_at": s.created_at,
        }
        for s in stories
    ]


@router.post("/folders/{folder_id}/add")
def add_story_to_folder(request, folder_id: int, payload: FolderAddStoryRequest):
    """Add a story to a folder."""
    user = get_current_user(request)
    folder = StoryFolder.objects.filter(id=folder_id, user=user).first()
    if not folder:
        raise HttpError(404, "Folder not found")
    if not Story.objects.filter(id=payload.story_id).exists():
        raise HttpError(404, "Story not found")
    if StoryFolderMembership.objects.filter(folder=folder, story_id=payload.story_id).exists():
        return {"ok": True, "message": "Story already in folder"}
    StoryFolderMembership.objects.create(folder=folder, story_id=payload.story_id)
    return {"ok": True}


@router.delete("/folders/{folder_id}/stories/{story_id}")
def remove_story_from_folder(request, folder_id: int, story_id: int):
    """Remove a story from a folder."""
    user = get_current_user(request)
    folder = StoryFolder.objects.filter(id=folder_id, user=user).first()
    if not folder:
        raise HttpError(404, "Folder not found")
    StoryFolderMembership.objects.filter(folder=folder, story_id=story_id).delete()
    return {"ok": True}


# ── Series parts ─────────────────────────────────────────────────


@router.get("/{story_id}/series-parts")
def get_series_parts(request, story_id: int):
    """Return discovered series parts for a story."""
    story = Story.objects.filter(id=story_id).first()
    if not story:
        raise HttpError(404, "Story not found")

    # Always attempt fresh discovery when possible
    parts = None
    if story.author and story.title:
        try:
            parts = find_series_parts(story.author, story.title)
        except Exception:
            pass

    # Fall back to cached series_json
    if not parts and story.series_json:
        parts = story.series_json if isinstance(story.series_json, list) else None

    if not parts:
        return {"parts": [], "series_word_count": 0, "series_est_minutes": 0,
                "submitted_count": 0, "total_count": 0}

    # Persist fresh discovery results
    if story.series_json != parts:
        story.series_json = parts
        story.part_count = len(parts)
        story.save(update_fields=["series_json", "part_count"])

    # Sort by post date
    parts.sort(key=lambda p: p.get("created_utc", 0))

    # Build candidate URLs for lookup
    candidate_urls = set()
    for part in parts:
        raw_url = (part.get("url") or "").strip()
        if not raw_url:
            continue
        base_url = raw_url.rstrip("/")
        if not base_url:
            continue
        candidate_urls.add(base_url)
        candidate_urls.add(base_url + "/")
        try:
            parsed = urlparse(raw_url)
            netloc = parsed.netloc.lower()
            if netloc.startswith("www."):
                alt_netloc = netloc[4:]
            else:
                alt_netloc = "www." + netloc
            alt_url = parsed._replace(netloc=alt_netloc).geturl().rstrip("/")
            candidate_urls.add(alt_url)
            candidate_urls.add(alt_url + "/")
        except Exception:
            pass

    if candidate_urls:
        existing = {
            row["reddit_url"]: row["id"]
            for row in Story.objects.filter(reddit_url__in=candidate_urls).values("id", "reddit_url")
        }
    else:
        existing = {}

    canonical_existing: dict[tuple[str, str], int] = {}
    for db_url, db_id in existing.items():
        if db_url:
            key = _canonical_url_key(db_url)
            if key not in canonical_existing:
                canonical_existing[key] = db_id

    for part in parts:
        raw_part_url = part.get("url") or ""
        if raw_part_url:
            matched_id = canonical_existing.get(_canonical_url_key(raw_part_url))
        else:
            matched_id = None
        part["story_id"] = matched_id

    # Auto-submit missing parts
    missing_parts = [p for p in parts if not p.get("story_id")]
    if missing_parts:
        for mp in missing_parts:
            mp_url = (mp.get("url") or "").strip()
            if not mp_url:
                continue
            try:
                part_text = fetch_story_text(mp_url)
            except Exception:
                continue
            if not part_text or not part_text.strip():
                continue
            content_digest = hash_content(part_text)
            dup = Story.objects.filter(content_hash=content_digest).values_list("id", flat=True).first()
            if dup:
                mp["story_id"] = dup
                continue
            narration = clean_for_narration(part_text)
            try:
                new_story = Story.objects.create(
                    title=mp.get("title", "Unknown"),
                    author=story.author or "",
                    reddit_url=mp_url,
                    text_content=part_text,
                    narration_text=narration,
                    content_hash=content_digest,
                    part_count=len(parts),
                    series_json=parts,
                )
                mp["story_id"] = new_story.id
            except Exception:
                pass

    # Compute series-level word count
    submitted_ids = [p["story_id"] for p in parts if p.get("story_id")]
    series_word_count = 0
    if submitted_ids:
        for row in Story.objects.filter(id__in=submitted_ids).values_list("narration_text", "text_content"):
            source = row[0] or row[1] or ""
            series_word_count += len(source.split())

    return {
        "parts": parts,
        "series_word_count": series_word_count,
        "series_est_minutes": round(series_word_count / 150) if series_word_count else 0,
        "submitted_count": len(submitted_ids),
        "total_count": len(parts),
    }


# ── Playback position ───────────────────────────────────────────
# NOTE: These must be defined BEFORE the /{story_id} catch-all route


@router.post("/playback", response=PlaybackStateResponse)
def save_playback_position(request, payload: PlaybackStateRequest):
    """Save the current playback position for a story."""
    user = get_optional_user(request)
    if not user:
        return {"story_id": payload.story_id, "position_seconds": 0.0}

    if not Story.objects.filter(id=payload.story_id).exists():
        raise HttpError(404, "Story not found")

    state, created = PlaybackState.objects.update_or_create(
        user=user,
        story_id=payload.story_id,
        defaults={"position_seconds": payload.position_seconds},
    )

    return {
        "story_id": state.story_id,
        "user_id": state.user_id,
        "position_seconds": state.position_seconds,
        "updated_at": state.updated_at,
    }


@router.get("/playback/{story_id}", response=PlaybackStateResponse)
def get_playback_position(request, story_id: int):
    """Get the saved playback position for a story."""
    user = get_optional_user(request)
    if not user:
        return {"story_id": story_id, "position_seconds": 0.0}

    state = PlaybackState.objects.filter(user=user, story_id=story_id).first()
    if not state:
        return {"story_id": story_id, "position_seconds": 0.0}

    return {
        "story_id": state.story_id,
        "user_id": state.user_id,
        "position_seconds": state.position_seconds,
        "updated_at": state.updated_at,
    }


# ── Single story ─────────────────────────────────────────────────
# NOTE: This catch-all /{story_id} route MUST be last


@router.get("/{story_id}", response=StoryResponse)
def get_story(request, story_id: int):
    """Get a single story by ID."""
    story = Story.objects.filter(id=story_id).first()
    if not story:
        raise HttpError(404, "Story not found")
    return _story_to_response(story)
