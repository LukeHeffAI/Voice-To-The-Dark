"""Unit tests for app.services.reddit."""

import hashlib
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from services.reddit import (
    _cache_key,
    _extract_reddit_links,
    _likely_continuation,
    _strip_part_suffix,
    _extract_part_number,
    _titles_match,
    fetch_top_posts,
    fetch_story_text,
    fetch_post_metadata,
    find_series_parts,
    get_cache_info,
    get_cache_path_for_timeframe,
)


# ── _cache_key ───────────────────────────────────────────────────


class TestCacheKey:
    def test_returns_sha256_hex(self):
        url = "https://www.reddit.com/r/nosleep/top.json?t=day&limit=25"
        expected = hashlib.sha256(url.encode()).hexdigest()
        assert _cache_key(url) == expected

    def test_deterministic(self):
        url = "https://example.com/some/path"
        assert _cache_key(url) == _cache_key(url)

    def test_different_urls_produce_different_keys(self):
        assert _cache_key("https://a.com") != _cache_key("https://b.com")

    def test_empty_string(self):
        result = _cache_key("")
        expected = hashlib.sha256(b"").hexdigest()
        assert result == expected

    def test_returns_64_char_hex_string(self):
        result = _cache_key("anything")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_url_with_unicode(self):
        url = "https://example.com/path?q=caf\u00e9"
        expected = hashlib.sha256(url.encode()).hexdigest()
        assert _cache_key(url) == expected


# ── _extract_reddit_links ────────────────────────────────────────


class TestExtractRedditLinks:
    def test_finds_single_link(self):
        text = "Read part 2 here: https://www.reddit.com/r/nosleep/comments/abc123/my_story/"
        links = _extract_reddit_links(text)
        assert len(links) == 1
        assert "abc123" in links[0]

    def test_finds_multiple_links(self):
        text = (
            "Part 1: https://www.reddit.com/r/nosleep/comments/aaa/title_one/\n"
            "Part 2: https://www.reddit.com/r/nosleep/comments/bbb/title_two/"
        )
        links = _extract_reddit_links(text)
        assert len(links) == 2

    def test_ignores_non_nosleep_links(self):
        text = "Check out https://www.reddit.com/r/AskReddit/comments/xyz/some_post/"
        links = _extract_reddit_links(text)
        assert len(links) == 0

    def test_handles_http_without_www(self):
        text = "Link: https://reddit.com/r/nosleep/comments/abc/title/"
        links = _extract_reddit_links(text)
        assert len(links) == 1

    def test_handles_http_scheme(self):
        text = "Link: http://www.reddit.com/r/nosleep/comments/abc/title/"
        links = _extract_reddit_links(text)
        assert len(links) == 1

    def test_empty_text(self):
        assert _extract_reddit_links("") == []

    def test_no_links(self):
        assert _extract_reddit_links("This is just a normal story with no links.") == []

    def test_link_followed_by_parenthesis(self):
        """Markdown-style link: the URL ends before the closing paren."""
        text = "[Next](https://www.reddit.com/r/nosleep/comments/abc/title/)"
        links = _extract_reddit_links(text)
        assert len(links) == 1
        # The regex stops before the closing paren
        assert ")" not in links[0]

    def test_link_with_underscores_in_slug(self):
        text = "https://www.reddit.com/r/nosleep/comments/abc123/the_long_story_title/"
        links = _extract_reddit_links(text)
        assert len(links) == 1

    def test_link_without_trailing_slash(self):
        text = "https://www.reddit.com/r/nosleep/comments/abc123/title"
        links = _extract_reddit_links(text)
        assert len(links) == 1

    def test_multiline_text(self):
        text = (
            "First paragraph.\n\n"
            "https://www.reddit.com/r/nosleep/comments/aaa/first/\n\n"
            "Second paragraph.\n\n"
            "https://www.reddit.com/r/nosleep/comments/bbb/second/\n"
        )
        links = _extract_reddit_links(text)
        assert len(links) == 2


# ── _likely_continuation ─────────────────────────────────────────


class TestLikelyContinuation:
    def test_same_author_with_part_in_title(self):
        current = {"author": "writer1", "title": "My Story Part 1", "selftext": ""}
        next_post = {"author": "writer1", "title": "My Story Part 2", "selftext": ""}
        assert _likely_continuation(current, next_post) is True

    def test_same_author_with_chapter_in_title(self):
        current = {"author": "writer1", "title": "Horror Story", "selftext": ""}
        next_post = {"author": "writer1", "title": "Horror Story Chapter 3", "selftext": ""}
        assert _likely_continuation(current, next_post) is True

    def test_different_author_returns_false(self):
        current = {"author": "writer1", "title": "My Story Part 1", "selftext": ""}
        next_post = {"author": "writer2", "title": "My Story Part 2", "selftext": ""}
        assert _likely_continuation(current, next_post) is False

    def test_same_author_no_part_marker(self):
        current = {"author": "writer1", "title": "Random Title", "selftext": ""}
        next_post = {"author": "writer1", "title": "Different Title", "selftext": ""}
        assert _likely_continuation(current, next_post) is False

    def test_part_marker_in_selftext(self):
        current = {"author": "writer1", "title": "Title", "selftext": ""}
        next_post = {
            "author": "writer1",
            "title": "Title Continued",
            "selftext": "This is part 2 of my story.",
        }
        assert _likely_continuation(current, next_post) is True

    def test_chapter_in_selftext(self):
        current = {"author": "writer1", "title": "Title", "selftext": ""}
        next_post = {
            "author": "writer1",
            "title": "Title Continued",
            "selftext": "chapter 5 begins now",
        }
        assert _likely_continuation(current, next_post) is True

    def test_missing_author_fields(self):
        """When author is missing/empty, the author check is skipped, but
        part markers are still needed."""
        current = {"author": "", "title": "Title", "selftext": ""}
        next_post = {"author": "", "title": "Title Part 2", "selftext": ""}
        assert _likely_continuation(current, next_post) is True

    def test_none_author_fields(self):
        current = {"title": "Title", "selftext": ""}
        next_post = {"title": "Title Part 3", "selftext": ""}
        assert _likely_continuation(current, next_post) is True

    def test_case_insensitive_part_match(self):
        current = {"author": "a", "title": "Story", "selftext": ""}
        next_post = {"author": "a", "title": "Story PART 2", "selftext": ""}
        assert _likely_continuation(current, next_post) is True

    def test_part_with_no_space(self):
        """'part2' without a space — the regex uses \\s* so this should match."""
        current = {"author": "a", "title": "Story", "selftext": ""}
        next_post = {"author": "a", "title": "Story part2", "selftext": ""}
        assert _likely_continuation(current, next_post) is True


# ── _strip_part_suffix ───────────────────────────────────────────


class TestStripPartSuffix:
    def test_removes_part_number(self):
        assert _strip_part_suffix("My Horror Story Part 3") == "My Horror Story"

    def test_removes_chapter_number(self):
        assert _strip_part_suffix("The Dark House Chapter 7") == "The Dark House"

    def test_removes_pt_abbreviation(self):
        assert _strip_part_suffix("Story Title pt 2") == "Story Title"

    def test_removes_pt_dot_abbreviation(self):
        assert _strip_part_suffix("Story Title pt. 4") == "Story Title"

    def test_removes_ch_abbreviation(self):
        assert _strip_part_suffix("Story Title ch 10") == "Story Title"

    def test_removes_ch_dot_abbreviation(self):
        assert _strip_part_suffix("Story Title ch. 10") == "Story Title"

    def test_no_suffix_unchanged(self):
        assert _strip_part_suffix("A Normal Title") == "A Normal Title"

    def test_empty_string(self):
        assert _strip_part_suffix("") == ""

    def test_removes_with_dash_separator(self):
        assert _strip_part_suffix("My Story - Part 2") == "My Story"

    def test_removes_with_colon_separator(self):
        assert _strip_part_suffix("My Story: Part 5") == "My Story"

    def test_removes_with_pipe_separator(self):
        assert _strip_part_suffix("My Story | Part 1") == "My Story"

    def test_removes_with_en_dash(self):
        assert _strip_part_suffix("My Story \u2013 Part 3") == "My Story"

    def test_removes_with_em_dash(self):
        assert _strip_part_suffix("My Story \u2014 Part 3") == "My Story"

    def test_part_only(self):
        """A title that is *only* a part suffix."""
        result = _strip_part_suffix("Part 1")
        assert result == ""

    def test_case_insensitive(self):
        assert _strip_part_suffix("Story PART 2") == "Story"
        assert _strip_part_suffix("Story Chapter 3") == "Story"

    def test_preserves_part_in_middle(self):
        """'part' in the middle of a title should not be stripped unless it
        matches the suffix pattern at the end."""
        result = _strip_part_suffix("The Apartment Complex")
        assert result == "The Apartment Complex"

    def test_trailing_text_after_part_number(self):
        """Pattern uses .* after the number, so extra text is also removed."""
        result = _strip_part_suffix("My Story Part 3 (Final)")
        assert result == "My Story"


# ── _extract_part_number ─────────────────────────────────────────


class TestExtractPartNumber:
    def test_part_number(self):
        assert _extract_part_number("My Story Part 3") == 3

    def test_chapter_number(self):
        assert _extract_part_number("Dark House Chapter 12") == 12

    def test_pt_abbreviation(self):
        assert _extract_part_number("Story pt 5") == 5

    def test_pt_dot_abbreviation(self):
        assert _extract_part_number("Story pt. 7") == 7

    def test_ch_abbreviation(self):
        assert _extract_part_number("Story ch 2") == 2

    def test_ch_dot_abbreviation(self):
        assert _extract_part_number("Story ch. 9") == 9

    def test_no_part_number(self):
        assert _extract_part_number("A Normal Title") is None

    def test_empty_string(self):
        assert _extract_part_number("") is None

    def test_case_insensitive(self):
        assert _extract_part_number("Story PART 4") == 4
        assert _extract_part_number("Story chapter 1") == 1

    def test_returns_first_match(self):
        """If multiple part markers exist, returns the first."""
        result = _extract_part_number("Part 2 - Chapter 5")
        assert result == 2

    def test_large_number(self):
        assert _extract_part_number("My Story Part 100") == 100

    def test_part_1(self):
        assert _extract_part_number("Beginning Part 1") == 1

    def test_part_with_no_space(self):
        assert _extract_part_number("Story part3") == 3


# ── _titles_match ────────────────────────────────────────────────


class TestTitlesMatch:
    def test_exact_match(self):
        assert _titles_match("my horror story", "my horror story") is True

    def test_empty_a(self):
        assert _titles_match("", "something") is False

    def test_empty_b(self):
        assert _titles_match("something", "") is False

    def test_both_empty(self):
        assert _titles_match("", "") is False

    def test_prefix_match_long_enough(self):
        """Shorter title is >= 10 chars, so prefix match succeeds."""
        base_a = "the haunted house on elm street"
        base_b = "the haunted house on elm street extended"
        assert _titles_match(base_a, base_b) is True

    def test_prefix_match_too_short(self):
        """Shorter title is < 10 chars, prefix match is rejected."""
        assert _titles_match("short", "short and more") is False

    def test_prefix_match_exactly_10_chars(self):
        """Shorter title is exactly 10 chars -- should match."""
        assert _titles_match("0123456789", "0123456789 extra") is True

    def test_no_match(self):
        assert _titles_match("story about ghosts", "story about vampires") is False

    def test_order_independent(self):
        """Matching works regardless of which is shorter."""
        a = "i found something in my basement"
        b = "i found something in my basement update"
        assert _titles_match(a, b) is True
        assert _titles_match(b, a) is True

    def test_prefix_at_9_chars_fails(self):
        """9-character prefix should not match."""
        assert _titles_match("123456789", "123456789 more text") is False

    def test_completely_different(self):
        assert _titles_match("alpha bravo charlie", "delta echo foxtrot") is False


# ── fetch_top_posts (mocked) ─────────────────────────────────────


class TestFetchTopPosts:
    @patch("services.reddit._reddit_get")
    def test_returns_enriched_posts(self, mock_get):
        mock_get.return_value = {
            "data": {
                "children": [
                    {
                        "data": {
                            "title": "A Scary Story",
                            "permalink": "/r/nosleep/comments/abc/a_scary_story/",
                            "ups": 1500,
                            "id": "abc",
                            "author": "spookywriter",
                            "selftext": "It was a dark night...",
                            "gilded": 2,
                            "author_flair_text": "Flair",
                            "link_flair_text": "Series",
                        }
                    }
                ]
            }
        }

        results = fetch_top_posts("today", limit=10)

        assert len(results) == 1
        post = results[0]
        assert post["title"] == "A Scary Story"
        assert post["url"] == "https://reddit.com/r/nosleep/comments/abc/a_scary_story/"
        assert post["score"] == 1500
        assert post["id"] == "abc"
        assert post["author"] == "spookywriter"
        assert post["selftext"] == "It was a dark night..."
        assert post["gilded"] == 2
        assert post["flair"] == "Flair"
        assert post["series_flair"] == "Series"

    @patch("services.reddit._reddit_get")
    def test_empty_response(self, mock_get):
        mock_get.return_value = {"data": {"children": []}}
        results = fetch_top_posts("week")
        assert results == []

    @patch("services.reddit._reddit_get")
    def test_missing_data_key(self, mock_get):
        mock_get.return_value = {}
        results = fetch_top_posts("month")
        assert results == []

    @patch("services.reddit._reddit_get")
    def test_timeframe_mapping(self, mock_get):
        mock_get.return_value = {"data": {"children": []}}

        for tf, expected_t in [
            ("today", "day"),
            ("week", "week"),
            ("month", "month"),
            ("year", "year"),
            ("alltime", "all"),
        ]:
            fetch_top_posts(tf)
            call_kwargs = mock_get.call_args
            params = call_kwargs[1].get("params") or call_kwargs[0][1]
            assert params["t"] == expected_t, f"timeframe '{tf}' should map to '{expected_t}'"

    @patch("services.reddit._reddit_get")
    def test_unknown_timeframe_defaults_to_day(self, mock_get):
        mock_get.return_value = {"data": {"children": []}}
        fetch_top_posts("unknown_value")
        call_kwargs = mock_get.call_args
        params = call_kwargs[1].get("params") or call_kwargs[0][1]
        assert params["t"] == "day"

    @patch("services.reddit._reddit_get")
    def test_custom_cache_ttl(self, mock_get):
        mock_get.return_value = {"data": {"children": []}}
        fetch_top_posts("today", cache_ttl=60)
        _, kwargs = mock_get.call_args
        assert kwargs["cache_ttl"] == 60

    @patch("services.reddit._reddit_get")
    def test_default_cache_ttl_is_listing_ttl(self, mock_get):
        mock_get.return_value = {"data": {"children": []}}
        fetch_top_posts("today")
        _, kwargs = mock_get.call_args
        # Default TTL should be CACHE_TTL_LISTING (604800)
        assert kwargs["cache_ttl"] == 604800

    @patch("services.reddit._reddit_get")
    def test_multiple_posts(self, mock_get):
        mock_get.return_value = {
            "data": {
                "children": [
                    {"data": {"title": f"Story {i}", "permalink": f"/r/nosleep/comments/{i}/s/", "id": str(i)}}
                    for i in range(5)
                ]
            }
        }
        results = fetch_top_posts("today", limit=5)
        assert len(results) == 5
        assert results[0]["title"] == "Story 0"
        assert results[4]["title"] == "Story 4"

    @patch("services.reddit._reddit_get")
    def test_score_fallback_to_score_field(self, mock_get):
        """When 'ups' is missing, should fall back to 'score'."""
        mock_get.return_value = {
            "data": {
                "children": [
                    {"data": {"title": "Story", "permalink": "/r/nosleep/comments/x/s/", "score": 999}}
                ]
            }
        }
        results = fetch_top_posts("today")
        assert results[0]["score"] == 999


# ── fetch_story_text (mocked) ────────────────────────────────────


class TestFetchStoryText:
    @patch("services.reddit._fetch_post_data")
    def test_returns_selftext(self, mock_fetch):
        mock_fetch.return_value = {
            "selftext": "It was a dark and stormy night...",
            "title": "Scary Story",
            "author": "writer",
            "id": "abc",
        }
        result = fetch_story_text("https://reddit.com/r/nosleep/comments/abc/scary_story/")
        assert result == "It was a dark and stormy night..."

    @patch("services.reddit._fetch_post_data")
    def test_empty_selftext(self, mock_fetch):
        mock_fetch.return_value = {
            "selftext": "",
            "title": "Title",
            "author": "writer",
            "id": "abc",
        }
        result = fetch_story_text("https://reddit.com/r/nosleep/comments/abc/title/")
        assert result == ""

    @patch("services.reddit._fetch_post_data")
    def test_missing_selftext_key(self, mock_fetch):
        mock_fetch.return_value = {
            "title": "Title",
            "author": "writer",
            "id": "abc",
        }
        result = fetch_story_text("https://reddit.com/r/nosleep/comments/abc/title/")
        assert result == ""


# ── fetch_post_metadata (mocked) ─────────────────────────────────


class TestFetchPostMetadata:
    @patch("services.reddit._fetch_post_data")
    def test_returns_full_metadata(self, mock_fetch):
        expected = {
            "title": "Scary Story",
            "selftext": "The story text.",
            "author": "writer",
            "id": "abc",
            "link_flair_text": "Series",
            "permalink": "/r/nosleep/comments/abc/scary_story/",
            "created_utc": 1700000000.0,
        }
        mock_fetch.return_value = expected
        result = fetch_post_metadata("https://reddit.com/r/nosleep/comments/abc/scary_story/")
        assert result == expected

    @patch("services.reddit._fetch_post_data")
    def test_passes_url_through(self, mock_fetch):
        mock_fetch.return_value = {"title": "", "selftext": "", "author": "", "id": ""}
        url = "https://reddit.com/r/nosleep/comments/xyz/story/"
        fetch_post_metadata(url)
        mock_fetch.assert_called_once_with(url)


# ── find_series_parts (mocked) ───────────────────────────────────


class TestFindSeriesParts:
    def _make_author_response(self, posts):
        """Helper to build a mock author page response."""
        children = []
        for p in posts:
            children.append({
                "data": {
                    "title": p.get("title", ""),
                    "permalink": p.get("permalink", ""),
                    "id": p.get("id", ""),
                    "subreddit": p.get("subreddit", "nosleep"),
                    "created_utc": p.get("created_utc", 0),
                }
            })
        return {"data": {"children": children}}

    @patch("services.reddit._reddit_get")
    def test_finds_matching_series_parts(self, mock_get):
        mock_get.return_value = self._make_author_response([
            {"title": "The Haunted House Part 1", "permalink": "/r/nosleep/comments/a/t1/", "id": "a", "created_utc": 100},
            {"title": "The Haunted House Part 2", "permalink": "/r/nosleep/comments/b/t2/", "id": "b", "created_utc": 200},
            {"title": "The Haunted House Part 3", "permalink": "/r/nosleep/comments/c/t3/", "id": "c", "created_utc": 300},
        ])

        results = find_series_parts("writer", "The Haunted House Part 1")
        assert len(results) == 3
        assert results[0]["part_number"] == 1
        assert results[1]["part_number"] == 2
        assert results[2]["part_number"] == 3

    @patch("services.reddit._reddit_get")
    def test_sorted_by_created_utc(self, mock_get):
        mock_get.return_value = self._make_author_response([
            {"title": "The Haunted House Part 3", "permalink": "/r/nosleep/comments/c/t3/", "id": "c", "created_utc": 300},
            {"title": "The Haunted House Part 1", "permalink": "/r/nosleep/comments/a/t1/", "id": "a", "created_utc": 100},
            {"title": "The Haunted House Part 2", "permalink": "/r/nosleep/comments/b/t2/", "id": "b", "created_utc": 200},
        ])

        results = find_series_parts("writer", "The Haunted House Part 2")
        assert results[0]["created_utc"] == 100
        assert results[1]["created_utc"] == 200
        assert results[2]["created_utc"] == 300

    @patch("services.reddit._reddit_get")
    def test_excludes_non_nosleep_posts(self, mock_get):
        mock_get.return_value = self._make_author_response([
            {"title": "The Haunted House Part 1", "permalink": "/r/nosleep/comments/a/t/", "id": "a", "subreddit": "nosleep", "created_utc": 100},
            {"title": "The Haunted House Part 2", "permalink": "/r/AskReddit/comments/b/t/", "id": "b", "subreddit": "AskReddit", "created_utc": 200},
        ])

        results = find_series_parts("writer", "The Haunted House Part 1")
        assert len(results) == 1

    @patch("services.reddit._reddit_get")
    def test_excludes_unrelated_titles(self, mock_get):
        mock_get.return_value = self._make_author_response([
            {"title": "The Haunted House Part 1", "permalink": "/r/nosleep/comments/a/t/", "id": "a", "created_utc": 100},
            {"title": "Totally Different Story", "permalink": "/r/nosleep/comments/b/t/", "id": "b", "created_utc": 200},
        ])

        results = find_series_parts("writer", "The Haunted House Part 1")
        assert len(results) == 1
        assert results[0]["title"] == "The Haunted House Part 1"

    def test_empty_author(self):
        """Empty author should return [] without any network call."""
        results = find_series_parts("", "Some Title")
        assert results == []

    @patch("services.reddit._reddit_get")
    def test_empty_base_title_after_stripping(self, mock_get):
        """If the title is only a part suffix (e.g. 'Part 1'), base becomes
        empty and should return []."""
        mock_get.return_value = self._make_author_response([])
        results = find_series_parts("writer", "Part 1")
        assert results == []

    @patch("services.reddit._reddit_get")
    def test_network_failure_returns_empty(self, mock_get):
        mock_get.side_effect = RuntimeError("Network error")
        results = find_series_parts("writer", "The Haunted House Part 1")
        assert results == []

    @patch("services.reddit._reddit_get")
    def test_result_structure(self, mock_get):
        mock_get.return_value = self._make_author_response([
            {"title": "The Haunted House Part 1", "permalink": "/r/nosleep/comments/a/t/", "id": "a", "created_utc": 100},
        ])

        results = find_series_parts("writer", "The Haunted House Part 1")
        assert len(results) == 1
        r = results[0]
        assert "title" in r
        assert "url" in r
        assert "id" in r
        assert "part_number" in r
        assert "created_utc" in r
        assert r["url"] == "https://reddit.com/r/nosleep/comments/a/t/"
        assert r["id"] == "a"
        assert r["part_number"] == 1
        assert r["created_utc"] == 100

    @patch("services.reddit._reddit_get")
    def test_no_part_number_in_title(self, mock_get):
        """A post that matches the base title but has no part number."""
        mock_get.return_value = self._make_author_response([
            {"title": "The Haunted House", "permalink": "/r/nosleep/comments/a/t/", "id": "a", "created_utc": 100},
            {"title": "The Haunted House Part 2", "permalink": "/r/nosleep/comments/b/t/", "id": "b", "created_utc": 200},
        ])

        results = find_series_parts("writer", "The Haunted House Part 2")
        assert len(results) == 2
        assert results[0]["part_number"] is None
        assert results[1]["part_number"] == 2

    @patch("services.reddit._reddit_get")
    def test_title_matching_is_case_insensitive(self, mock_get):
        mock_get.return_value = self._make_author_response([
            {"title": "THE HAUNTED HOUSE Part 1", "permalink": "/r/nosleep/comments/a/t/", "id": "a", "created_utc": 100},
        ])

        results = find_series_parts("writer", "the haunted house Part 2")
        assert len(results) == 1

    @patch("services.reddit._reddit_get")
    def test_prefix_matching_for_title_variations(self, mock_get):
        mock_get.return_value = self._make_author_response([
            {"title": "The Haunted House on Elm Street Part 1", "permalink": "/r/nosleep/comments/a/t/", "id": "a", "created_utc": 100},
            {"title": "The Haunted House on Elm Street Extended Part 2", "permalink": "/r/nosleep/comments/b/t/", "id": "b", "created_utc": 200},
        ])

        results = find_series_parts("writer", "The Haunted House on Elm Street Part 1")
        # "the haunted house on elm street" is >= 10 chars, and "the haunted house on elm street extended"
        # starts with it, so both should match
        assert len(results) == 2


# ── get_cache_path_for_timeframe ─────────────────────────────────


class TestGetCachePathForTimeframe:
    def test_returns_path_object(self):
        result = get_cache_path_for_timeframe("today")
        assert isinstance(result, Path)

    def test_path_ends_with_json(self):
        result = get_cache_path_for_timeframe("week")
        assert result.suffix == ".json"

    def test_path_is_in_cache_dir(self):
        result = get_cache_path_for_timeframe("month")
        assert "reddit_cache" in str(result)

    def test_different_timeframes_different_paths(self):
        p1 = get_cache_path_for_timeframe("today")
        p2 = get_cache_path_for_timeframe("week")
        assert p1 != p2

    def test_same_timeframe_same_path(self):
        p1 = get_cache_path_for_timeframe("alltime")
        p2 = get_cache_path_for_timeframe("alltime")
        assert p1 == p2

    def test_unknown_timeframe_defaults_to_day(self):
        """Unknown timeframe maps to 'day', same as 'today'."""
        p_unknown = get_cache_path_for_timeframe("bogus")
        p_today = get_cache_path_for_timeframe("today")
        assert p_unknown == p_today

    def test_custom_limit_changes_path(self):
        p1 = get_cache_path_for_timeframe("today", limit=25)
        p2 = get_cache_path_for_timeframe("today", limit=50)
        assert p1 != p2


# ── get_cache_info ───────────────────────────────────────────────


class TestGetCacheInfo:
    def test_returns_dict_with_all_timeframes(self):
        info = get_cache_info()
        expected_keys = {"today", "week", "month", "year", "alltime"}
        assert set(info.keys()) == expected_keys

    def test_nonexistent_cache_returns_none(self, tmp_path):
        """When cache files don't exist, values should be None."""
        with patch("services.reddit._get_cache_dir", return_value=tmp_path / "nonexistent"):
            info = get_cache_info()
            for tf, mtime in info.items():
                assert mtime is None

    def test_existing_cache_returns_mtime(self, tmp_path):
        """When a cache file exists, its mtime should be returned."""
        with patch("services.reddit._get_cache_dir", return_value=tmp_path):
            # Write a cache file for "today"
            path = get_cache_path_for_timeframe("today")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}")

            info = get_cache_info()
            assert info["today"] is not None
            assert isinstance(info["today"], float)
