# app/services/reddit.py

import re
import json
import time
import hashlib
import logging
from typing import List, Dict, Set, Optional
from pathlib import Path
from urllib.parse import urlencode

import requests

logger = logging.getLogger(__name__)

# ── Cache configuration ──────────────────────────────────────────
CACHE_DIR = Path("data/reddit_cache")
CACHE_TTL_LISTING = 3600       # 1 hour for top-posts / author-page listings
CACHE_TTL_POST = 86400         # 24 hours for individual posts (text rarely changes)

# ── HTTP session ─────────────────────────────────────────────────
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "VoiceToTheDark/1.0 (horror narrator app; +github.com/LukeHeffAI/Voice-To-The-Dark)",
})

REDDIT_BASE = "https://www.reddit.com"


# ── Low-level helpers ────────────────────────────────────────────

def _cache_key(url: str) -> str:
    """SHA256 hash of the full URL for use as a cache filename."""
    return hashlib.sha256(url.encode()).hexdigest()


def _reddit_get(url: str, params: Optional[dict] = None, cache_ttl: int = CACHE_TTL_LISTING) -> dict:
    """Fetch a Reddit .json endpoint with disk-based caching and retry.

    1. Build the full URL (append .json if needed).
    2. Check disk cache — return cached data if fresh enough.
    3. Otherwise GET from Reddit, retrying on 429 with exponential backoff.
    4. Save the response to disk cache and return parsed JSON.
    """
    # Normalise URL — strip trailing slashes, append .json
    url = url.rstrip("/")
    if not url.endswith(".json"):
        url += ".json"

    if params:
        url = url + "?" + urlencode(params)

    # ── Check cache ──
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{_cache_key(url)}.json"

    if cache_file.exists():
        age = time.time() - cache_file.stat().st_mtime
        if age < cache_ttl:
            logger.debug("Cache hit for %s (age %.0fs)", url, age)
            return json.loads(cache_file.read_text(encoding="utf-8"))
        logger.debug("Cache stale for %s (age %.0fs > ttl %ds)", url, age, cache_ttl)

    # ── Fetch from Reddit ──
    last_exc: Optional[Exception] = None
    for attempt in range(4):  # up to 4 attempts
        try:
            resp = SESSION.get(url, timeout=15)
            if resp.status_code == 429:
                wait = 2 ** attempt
                logger.warning("Reddit 429 — retrying in %ds (attempt %d)", wait, attempt + 1)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            # ── Save to cache ──
            cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return data
        except Exception as exc:
            last_exc = exc
            if attempt < 3:
                wait = 2 ** attempt
                logger.warning("Reddit request failed (%s) — retrying in %ds", exc, wait)
                time.sleep(wait)

    raise RuntimeError(f"Failed to fetch {url} after 4 attempts: {last_exc}")


# ── Post data helpers ────────────────────────────────────────────

def _fetch_post_data(post_url: str) -> dict:
    """Fetch a single post's data dict from its Reddit URL.

    Returns a dict with keys: title, selftext, author, id, link_flair_text, permalink.
    Uses a 24-hour cache TTL since story text rarely changes.
    """
    raw = _reddit_get(post_url, cache_ttl=CACHE_TTL_POST)

    # Individual post .json returns a list of two listings
    # [0] = the post itself, [1] = comments
    if isinstance(raw, list) and len(raw) >= 1:
        post = raw[0]["data"]["children"][0]["data"]
    else:
        raise ValueError(f"Unexpected response structure from {post_url}")

    return {
        "title": post.get("title", ""),
        "selftext": post.get("selftext", ""),
        "author": post.get("author", ""),
        "id": post.get("id", ""),
        "link_flair_text": post.get("link_flair_text"),
        "permalink": post.get("permalink", ""),
    }


def fetch_post_metadata(post_url: str) -> dict:
    """Public wrapper — returns post metadata (title, author, etc.) for a URL."""
    return _fetch_post_data(post_url)


def fetch_post_title(post_url: str) -> str:
    """Return just the title string for a Reddit post URL."""
    return _fetch_post_data(post_url)["title"]


# ── Top posts listing ────────────────────────────────────────────

def fetch_top_posts(timeframe: str = "today", limit: int = 25) -> List[Dict]:
    """Fetch the top NoSleep posts for a given timeframe.

    Returns a list of dicts with enriched metadata per post.
    The listing .json already contains selftext, author, gilding, flair — so
    no per-post requests are needed.
    """
    time_filter_map = {
        "today": "day",
        "week": "week",
        "month": "month",
        "year": "year",
        "alltime": "all",
    }
    time_filter = time_filter_map.get(timeframe, "day")

    url = f"{REDDIT_BASE}/r/nosleep/top.json"
    params = {"t": time_filter, "limit": str(limit)}
    data = _reddit_get(url, params=params, cache_ttl=CACHE_TTL_LISTING)

    results = []
    for child in data.get("data", {}).get("children", []):
        post = child.get("data", {})
        results.append({
            "title": post.get("title", ""),
            "url": f"https://reddit.com{post.get('permalink', '')}",
            "score": post.get("ups", post.get("score", 0)),
            "id": post.get("id", ""),
            "author": post.get("author", ""),
            "gilded": post.get("gilded", 0),
            "flair": post.get("author_flair_text"),
            "series_flair": post.get("link_flair_text"),
        })
    return results


# ── Single-post text fetch ───────────────────────────────────────

def fetch_story_text(post_url: str) -> str:
    """Return the selftext for a single post (no multi-part logic)."""
    return _fetch_post_data(post_url).get("selftext", "")


# ── Multi-part story fetching ────────────────────────────────────

def fetch_multi_part_story(post_url: str) -> str:
    """Fetch the text for a story that may have multiple parts.

    1. Fetch the primary post's text.
    2. Look for explicit next-part links in the body text.
    3. Recursively fetch linked parts.
    4. Combine all parts with separator.

    All sub-requests go through the disk cache.
    """
    visited_ids: Set[str] = set()
    combined = _gather_story_parts(post_url, visited_ids)
    return combined


def _gather_story_parts(post_url: str, visited_ids: Set[str]) -> str:
    """Recursively gather text from this post and any linked next-part posts."""
    post = _fetch_post_data(post_url)

    if post["id"] in visited_ids:
        return ""
    visited_ids.add(post["id"])

    story_text = post.get("selftext", "")

    # Find explicit Reddit links in the text pointing to next parts
    next_links = _extract_reddit_links(story_text)

    for link in next_links:
        try:
            next_post = _fetch_post_data(link)
            if _likely_continuation(post, next_post):
                part_text = _gather_story_parts(link, visited_ids)
                if part_text:
                    story_text += f"\n\n---\n\n{part_text}"
        except Exception:
            pass  # skip broken links

    return story_text


# ── Series parts discovery (author page) ─────────────────────────

def find_series_parts(author: str, title: str) -> List[Dict]:
    """Search an author's top submissions for posts that look like parts of
    the same series as *title*.

    Returns a list of dicts sorted by detected part number:
        [{"title": str, "url": str, "id": str, "part_number": int|None}, ...]
    """
    if not author:
        return []

    url = f"{REDDIT_BASE}/user/{author}/submitted.json"
    params = {"sort": "top", "limit": "100"}

    try:
        data = _reddit_get(url, params=params, cache_ttl=CACHE_TTL_LISTING)
    except Exception:
        logger.warning("Failed to fetch author page for u/%s", author)
        return []

    # Strip common part/chapter suffixes to get the "base" title for matching
    base_title = _strip_part_suffix(title).lower().strip()
    if not base_title:
        return []

    results = []
    for child in data.get("data", {}).get("children", []):
        post = child.get("data", {})
        # Only r/nosleep posts
        if post.get("subreddit", "").lower() != "nosleep":
            continue
        post_title = post.get("title", "")
        post_base = _strip_part_suffix(post_title).lower().strip()

        # Match if base titles are similar enough
        if not _titles_match(base_title, post_base):
            continue

        part_num = _extract_part_number(post_title)
        results.append({
            "title": post_title,
            "url": f"https://reddit.com{post.get('permalink', '')}",
            "id": post.get("id", ""),
            "part_number": part_num,
        })

    # Sort by part number (None last)
    results.sort(key=lambda r: (r["part_number"] is None, r["part_number"] or 0))

    return results


# ── Helpers (pure logic, no network) ─────────────────────────────

def _extract_reddit_links(text: str) -> List[str]:
    """Find Reddit r/nosleep links in text."""
    pattern = r"https?://(?:www\.)?reddit\.com/r/nosleep/comments/[a-zA-Z0-9_]+/[^ )\r\n]*"
    return re.findall(pattern, text)


def _likely_continuation(current: dict, next_post: dict) -> bool:
    """Heuristic: is next_post likely a continuation of current?"""
    # Same author check
    if current.get("author") and next_post.get("author"):
        if current["author"] != next_post["author"]:
            return False

    # Title or text references "part X" or "chapter X"
    pattern = r"(part\s*\d+|chapter\s*\d+)"
    title_match = re.search(pattern, next_post.get("title", "").lower())
    text_match = re.search(pattern, next_post.get("selftext", "").lower())
    return bool(title_match or text_match)


_PART_PATTERN = re.compile(
    r"\s*[-–—:,|]*\s*(?:part|pt\.?|chapter|ch\.?)\s*\d+.*$",
    re.IGNORECASE,
)


def _strip_part_suffix(title: str) -> str:
    """Remove 'Part X', 'Chapter X' etc. from the end of a title."""
    return _PART_PATTERN.sub("", title).strip()


def _extract_part_number(title: str) -> Optional[int]:
    """Extract the part/chapter number from a title, or None."""
    m = re.search(r"(?:part|pt\.?|chapter|ch\.?)\s*(\d+)", title, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _titles_match(base_a: str, base_b: str) -> bool:
    """Check if two base titles (with part suffixes stripped) are similar enough."""
    if not base_a or not base_b:
        return False
    # Exact match after stripping
    if base_a == base_b:
        return True
    # One is a prefix of the other (handles slight title variations)
    shorter, longer = sorted([base_a, base_b], key=len)
    if longer.startswith(shorter) and len(shorter) >= 10:
        return True
    return False
