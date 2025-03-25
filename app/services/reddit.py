import os
from typing import List, Dict
import praw
from app.config import settings

# You might need: pip install praw

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
    # Map your custom timeframe to Reddit's actual timespan (e.g., 'day' vs. 'all')
    # For "all time", you might use 'top' with 'time_filter=all'
    # For "today", you might use 'top' with 'time_filter=day'
    if timeframe == "today":
        time_filter = "day"
    elif timeframe == "this_week":
        time_filter = "week"
    elif timeframe == "this_month":
        time_filter = "month"
    elif timeframe == "this_year":
        time_filter = "year"
    elif timeframe == "alltime":
        time_filter = "all"
    else:
        time_filter = "year"  # fallback
    
    reddit = init_reddit()
    subreddit = reddit.subreddit("nosleep")

    # Use .top(limit=...) for top posts, with specified time_filter
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


def fetch_story_text(post_url: str) -> str:
    """
    Fetch the text content for a single or multi-part story 
    from a given Reddit post URL.
    
    Return the combined text as a single string.
    """
    reddit = init_reddit()
    
    # E.g., parse the Reddit post ID from the URL
    # A typical pattern for URLs is: https://www.reddit.com/r/nosleep/comments/<id>/some_title/
    # You can parse out <id> or pass the full url to reddit.submission(url=post_url)
    
    submission = reddit.submission(url=post_url)
    submission_text = submission.selftext  # The main body text

    # If you want to handle multi-part stories, you’d check:
    #  - does the text reference another post?
    #  - or check submission.comments for links or user references?
    # For now, returning just the single post text:
    return submission_text
