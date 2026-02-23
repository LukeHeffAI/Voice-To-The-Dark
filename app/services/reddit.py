# app/services/reddit.py

import re
from typing import List, Dict, Set
import praw
from app.config import settings

def init_reddit() -> praw.Reddit:
    """Initialize and return a Reddit client using PRAW."""
    reddit = praw.Reddit(
        client_id=settings.REDDIT_CLIENT_ID,
        client_secret=settings.REDDIT_CLIENT_SECRET,
        user_agent="horror_narrator/0.1",
    )
    return reddit

def fetch_top_posts(timeframe: str = "today", limit: int = 25) -> List[Dict]:
    """
    Fetch the top NoSleep posts for a given timeframe.
    timeframe can be 'today', 'alltime', etc.
    Returns a list of dicts with { 'title': ..., 'url': ..., 'score': ... }
    """
    if timeframe == "today":
        time_filter = "day"
    elif timeframe == "week":
        time_filter = "week"
    elif timeframe == "month":
        time_filter = "month"
    elif timeframe == "year":
        time_filter = "year"
    elif timeframe == "alltime":
        time_filter = "all"
    else:
        time_filter = "day"

    reddit = init_reddit()
    subreddit = reddit.subreddit("nosleep")

    # Use .top with time_filter
    top_posts = subreddit.top(limit=limit, time_filter=time_filter)

    results = []
    for post in top_posts:
        results.append({
            "title": post.title,
            "url": f"https://reddit.com{post.permalink}",
            "score": post.score,
            "id": post.id
        })
    return results

def fetch_multi_part_story(post_url: str) -> str:
    """
    Fetch the text for a story that may have multiple parts.
    1. Parse the primary post's text.
    2. Look for 'Part' references or explicit next-part links.
    3. Recursively fetch additional posts.
    4. Combine all text into a single string.
    
    Returns the combined text for all parts discovered.
    """
    reddit = init_reddit()
    submission = reddit.submission(url=post_url)
    visited_ids = set()  # track visited post IDs to avoid loops

    combined_text = _gather_story_parts(submission, reddit, visited_ids)
    return combined_text

def _gather_story_parts(submission, reddit, visited_ids: Set[str]) -> str:
    """
    Recursively gather text from this submission and any linked 'next part' submissions.
    Avoid infinite loops with visited_ids.
    """
    if submission.id in visited_ids:
        return ""  # Already included

    visited_ids.add(submission.id)

    # Grab the base text
    story_text = submission.selftext or ""

    # Check if the title or text references a possible "part" number
    # (This is mostly for show; the more valuable step is to find actual links to next part)
    # For demonstration, we won't do much with it except keep note.

    # Find any reddit links in the text that might point to next part
    # e.g., https://www.reddit.com/r/nosleep/comments/<id>/...
    # Some authors just paste the link with "Next: https://..."
    next_links = _extract_reddit_links(story_text)

    # Optionally, you can also look at top-level comments for a link to next part, etc.
    # For this example, we'll stick to in-body links.

    # Recursively gather from next parts
    for link in next_links:
        # Convert link to a submission and gather text
        try:
            next_sub = reddit.submission(url=link)
            # Heuristics: If the next_sub title has "Part" + # and the same original author, let's accept it
            # or you can skip author check, it's up to you
            if _likely_continuation(submission, next_sub):
                part_text = _gather_story_parts(next_sub, reddit, visited_ids)
                if part_text:
                    story_text += f"\n\n---\n\n{part_text}"
        except Exception:
            # In case the link isn't valid or PRAW fails
            pass

    return story_text

def _extract_reddit_links(text: str) -> List[str]:
    """
    Find potential Reddit links in text that match standard reddit.com pattern.
    E.g., (https://reddit.com/r/nosleep/comments/...) or
           (https://www.reddit.com/r/nosleep/comments/...)
    """
    pattern = r"https?://(?:www\.)?reddit\.com/r/nosleep/comments/[a-zA-Z0-9_]+/[^ )\r\n]*"
    return re.findall(pattern, text)

def _likely_continuation(current_sub, next_sub) -> bool:
    """
    Simple heuristic to see if next_sub is likely a continuation:
    1. Same author, or no strict check if you want to allow cross-posted
    2. Title or body references 'Part 2', 'Part 3', etc.
    3. Could get more elaborate if you want
    """
    # Check same author or skip if you want
    if current_sub.author and next_sub.author:
        if current_sub.author.name != next_sub.author.name:
            return False

    # Check if next_sub.title has 'part x' or similar
    pattern = r"(part\s*\d+|chapter\s*\d+)"
    title_match = re.search(pattern, next_sub.title.lower())
    text_match = re.search(pattern, next_sub.selftext.lower())
    return bool(title_match or text_match)


def fetch_story_text(post_url: str) -> str:
    """
    A convenience method if you don't want multi-part logic:
    Return single post text only.
    """
    reddit = init_reddit()
    submission = reddit.submission(url=post_url)
    return submission.selftext or ""