"""Tests for the /stories router endpoints."""

import pytest
from unittest.mock import patch
from app.models.story import Story, PlaybackState, User


class TestListStories:
    def test_empty_list(self, client, db_session):
        resp = client.get("/stories/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_stories(self, client, sample_story, db_session):
        resp = client.get("/stories/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "The Haunted House"
        assert data[0]["has_audio"] is False
        assert data[0]["has_script"] is False


class TestGetStory:
    def test_get_existing(self, client, sample_story, db_session):
        resp = client.get(f"/stories/{sample_story.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "The Haunted House"
        assert data["id"] == sample_story.id

    def test_get_nonexistent(self, client, db_session):
        resp = client.get("/stories/9999")
        assert resp.status_code == 404


class TestCheckDuplicate:
    def test_no_duplicate(self, client, db_session):
        resp = client.get("/stories/check-duplicate/", params={
            "reddit_url": "https://reddit.com/r/nosleep/comments/new/new_story/"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_duplicate"] is False

    def test_finds_duplicate(self, client, sample_story, db_session):
        resp = client.get("/stories/check-duplicate/", params={
            "reddit_url": sample_story.reddit_url
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_duplicate"] is True
        assert data["existing_story_id"] == sample_story.id


class TestTopNosleep:
    @patch("app.services.reddit.fetch_top_posts")
    def test_returns_posts(self, mock_fetch, client, db_session):
        mock_fetch.return_value = [
            {"title": "A Scary Story", "url": "https://reddit.com/r/nosleep/comments/abc/story/",
             "score": 500, "id": "abc", "author": "ghost_writer", "gilded": 0,
             "flair": None, "series_flair": None},
        ]
        resp = client.get("/stories/top-nosleep?timeframe=alltime")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "A Scary Story"
        assert data[0]["already_submitted"] is False

    @patch("app.services.reddit.fetch_top_posts")
    def test_flags_already_submitted(self, mock_fetch, client, sample_story, db_session):
        mock_fetch.return_value = [
            {"title": "The Haunted House", "url": sample_story.reddit_url,
             "score": 1000, "id": "abc123", "author": "test", "gilded": 0,
             "flair": None, "series_flair": None},
        ]
        resp = client.get("/stories/top-nosleep")
        assert resp.status_code == 200
        assert resp.json()[0]["already_submitted"] is True

    @patch("app.services.reddit.fetch_top_posts")
    def test_reddit_unavailable_returns_502(self, mock_fetch, client, db_session):
        mock_fetch.side_effect = RuntimeError("Failed to fetch after 4 attempts")
        resp = client.get("/stories/top-nosleep")
        assert resp.status_code == 502
        assert "unreachable" in resp.json()["detail"].lower()


class TestSubmitStory:
    @patch("app.routers.stories.fetch_post_metadata")
    @patch("app.routers.stories.fetch_multi_part_story")
    def test_submit_new_story(self, mock_fetch, mock_metadata, client, auth_headers, db_session):
        mock_metadata.return_value = {"title": "My Scary Story", "author": "scary_author"}
        mock_fetch.return_value = "Once upon a time, in a dark forest, something terrible happened."

        resp = client.post("/stories/submit", json={
            "reddit_url": "https://www.reddit.com/r/nosleep/comments/xyz/my_scary_story/"
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "My Scary Story"
        assert data["author"] == "scary_author"
        assert data["part_count"] == 1

    @patch("app.routers.stories.fetch_post_metadata")
    @patch("app.routers.stories.fetch_multi_part_story")
    def test_submit_strips_query_string(self, mock_fetch, mock_metadata, client, auth_headers, db_session):
        """Query strings/fragments are stripped from the URL before fetching and storing."""
        mock_metadata.return_value = {"title": "Share Link Story", "author": "author"}
        mock_fetch.return_value = "Story text here."

        resp = client.post("/stories/submit", json={
            "reddit_url": "https://www.reddit.com/r/nosleep/comments/abc/share/?utm_source=share&utm_medium=web"
        }, headers=auth_headers)
        assert resp.status_code == 200
        # The stored URL should have no query string (trailing slash in path is preserved)
        assert resp.json()["reddit_url"] == "https://www.reddit.com/r/nosleep/comments/abc/share/"
        # The normalized URL was passed to the fetch helpers
        mock_metadata.assert_called_once_with("https://www.reddit.com/r/nosleep/comments/abc/share/")

    def test_submit_rejects_non_reddit_host(self, client, auth_headers, db_session):
        """SSRF: URLs not from reddit.com are rejected."""
        resp = client.post("/stories/submit", json={
            "reddit_url": "https://evil.com/r/nosleep/comments/xyz/story/"
        }, headers=auth_headers)
        assert resp.status_code == 400
        assert "host" in resp.json()["detail"].lower()

    def test_submit_rejects_non_nosleep_path(self, client, auth_headers, db_session):
        """URLs from reddit.com but not r/nosleep/comments are rejected."""
        resp = client.post("/stories/submit", json={
            "reddit_url": "https://www.reddit.com/r/horror/comments/xyz/story/"
        }, headers=auth_headers)
        assert resp.status_code == 400
        assert "nosleep" in resp.json()["detail"].lower()

    @patch("app.routers.stories.fetch_post_metadata")
    @patch("app.routers.stories.fetch_multi_part_story")
    def test_submit_returns_existing_on_duplicate_url(self, mock_fetch, mock_metadata, client, auth_headers, sample_story, db_session):
        """Submitting an existing URL returns the existing story (200, not error)."""
        resp = client.post("/stories/submit", json={
            "reddit_url": sample_story.reddit_url
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == sample_story.id
        # Reddit should NOT have been called
        mock_metadata.assert_not_called()

    def test_submit_requires_auth(self, client, db_session):
        resp = client.post("/stories/submit", json={
            "reddit_url": "https://www.reddit.com/r/nosleep/comments/xyz/story/"
        })
        assert resp.status_code == 401


class TestManualSubmitStory:
    def test_manual_submit_new_story(self, client, auth_headers, db_session):
        resp = client.post("/stories/submit-manual", json={
            "title": "My Manual Story",
            "text_content": "It was a dark and stormy night. The old house creaked.",
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "My Manual Story"
        assert data["part_count"] == 1
        assert data["reddit_url"] is None

    def test_manual_submit_with_reddit_url(self, client, auth_headers, db_session):
        resp = client.post("/stories/submit-manual", json={
            "title": "Story With Source",
            "text_content": "Something lurked in the shadows of the abandoned mall.",
            "reddit_url": "https://www.reddit.com/r/nosleep/comments/xyz/source/",
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Story With Source"
        assert data["reddit_url"] == "https://www.reddit.com/r/nosleep/comments/xyz/source/"

    def test_manual_submit_rejects_non_reddit_url(self, client, auth_headers, db_session):
        """SSRF: non-reddit.com URLs are rejected even in manual submit."""
        resp = client.post("/stories/submit-manual", json={
            "title": "A Story",
            "text_content": "Some content.",
            "reddit_url": "https://evil.com/r/nosleep/comments/xyz/story/",
        }, headers=auth_headers)
        assert resp.status_code == 400
        assert "host" in resp.json()["detail"].lower()

    def test_manual_submit_rejects_non_nosleep_reddit_url(self, client, auth_headers, db_session):
        """URLs from reddit.com but not r/nosleep/comments are rejected."""
        resp = client.post("/stories/submit-manual", json={
            "title": "A Story",
            "text_content": "Some content.",
            "reddit_url": "https://www.reddit.com/r/AskReddit/comments/xyz/story/",
        }, headers=auth_headers)
        assert resp.status_code == 400
        assert "nosleep" in resp.json()["detail"].lower()

    def test_manual_submit_duplicate_content(self, client, auth_headers, db_session):
        """Submitting the same text twice returns the existing story."""
        text = "The mirror showed a reflection that wasn't mine."
        resp1 = client.post("/stories/submit-manual", json={
            "title": "First Title",
            "text_content": text,
        }, headers=auth_headers)
        assert resp1.status_code == 200
        first_id = resp1.json()["id"]

        resp2 = client.post("/stories/submit-manual", json={
            "title": "Second Title",
            "text_content": text,
        }, headers=auth_headers)
        assert resp2.status_code == 200
        assert resp2.json()["id"] == first_id

    def test_manual_submit_empty_text(self, client, auth_headers, db_session):
        resp = client.post("/stories/submit-manual", json={
            "title": "Empty Story",
            "text_content": "   ",
        }, headers=auth_headers)
        assert resp.status_code == 400

    def test_manual_submit_empty_title(self, client, auth_headers, db_session):
        resp = client.post("/stories/submit-manual", json={
            "title": "   ",
            "text_content": "Some actual content here.",
        }, headers=auth_headers)
        assert resp.status_code == 400

    def test_manual_submit_requires_auth(self, client, db_session):
        resp = client.post("/stories/submit-manual", json={
            "title": "Unauthorized Story",
            "text_content": "This should not work.",
        })
        assert resp.status_code == 401

    def test_manual_submit_author_persisted(self, client, auth_headers, db_session):
        """Author provided in a pure manual (no-URL) submission is stored on the story."""
        resp = client.post("/stories/submit-manual", json={
            "title": "Authored Story",
            "text_content": "Content for the authored story goes here.",
            "author": "test_author",
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["author"] == "test_author"

    @patch("app.routers.stories.fetch_post_metadata")
    @patch("app.routers.stories.fetch_multi_part_story")
    def test_manual_submit_url_author_from_request(self, mock_fetch, mock_metadata, client, auth_headers, db_session):
        """When author is supplied alongside a URL, the request author takes precedence over Reddit metadata."""
        mock_metadata.return_value = {"title": "Reddit Title", "author": "reddit_author"}
        mock_fetch.return_value = "Full story text fetched from Reddit."

        resp = client.post("/stories/submit-manual", json={
            "reddit_url": "https://www.reddit.com/r/nosleep/comments/xyz/my_url_story/",
            "author": "override_author",
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["author"] == "override_author"

    @patch("app.routers.stories.fetch_post_metadata")
    @patch("app.routers.stories.fetch_multi_part_story")
    def test_manual_submit_url_author_fallback_from_reddit(self, mock_fetch, mock_metadata, client, auth_headers, db_session):
        """When author is omitted and a URL is provided, the author falls back to Reddit metadata."""
        mock_metadata.return_value = {"title": "Reddit Title", "author": "reddit_author"}
        mock_fetch.return_value = "Full story text fetched from Reddit."

        resp = client.post("/stories/submit-manual", json={
            "reddit_url": "https://www.reddit.com/r/nosleep/comments/xyz/my_url_story/",
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["author"] == "reddit_author"


class TestSeriesParts:
    def test_returns_empty_for_story_without_parts(self, client, sample_story, db_session):
        resp = client.get(f"/stories/{sample_story.id}/series-parts")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_404_for_nonexistent_story(self, client, db_session):
        resp = client.get("/stories/9999/series-parts")
        assert resp.status_code == 404

    def test_enriches_submitted_part_with_story_id(self, client, db_session):
        """A series part whose URL matches a submitted story gets the story_id."""
        import json
        submitted_url = "https://www.reddit.com/r/nosleep/comments/part1/part_one/"
        submitted = Story(
            title="Part 1",
            reddit_url=submitted_url,
            text_content="Part one content.",
            narration_text="Part one content.",
            content_hash="hash_part1",
            part_count=1,
        )
        db_session.add(submitted)

        parts = [
            {"title": "Part 1", "url": submitted_url},
            {"title": "Part 2", "url": "https://www.reddit.com/r/nosleep/comments/part2/part_two/"},
        ]
        series_story = Story(
            title="The Series",
            reddit_url="https://www.reddit.com/r/nosleep/comments/series/the_series/",
            text_content="Series content.",
            narration_text="Series content.",
            content_hash="hash_series",
            part_count=1,
            series_json=json.dumps(parts),
        )
        db_session.add(series_story)
        db_session.commit()
        db_session.refresh(submitted)
        db_session.refresh(series_story)

        resp = client.get(f"/stories/{series_story.id}/series-parts")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["story_id"] == submitted.id
        assert data[1]["story_id"] is None

    def test_enriches_part_with_trailing_slash_variant(self, client, db_session):
        """URL matching works when the DB URL has a trailing slash but the part URL does not."""
        import json
        submitted_url = "https://www.reddit.com/r/nosleep/comments/part1/part_one/"
        submitted = Story(
            title="Part 1",
            reddit_url=submitted_url,
            text_content="Content.",
            narration_text="Content.",
            content_hash="hash_trail",
            part_count=1,
        )
        db_session.add(submitted)

        # Part URL without trailing slash
        parts = [{"title": "Part 1", "url": submitted_url.rstrip("/")}]
        series_story = Story(
            title="Series",
            reddit_url="https://www.reddit.com/r/nosleep/comments/s/series/",
            text_content="Series.",
            narration_text="Series.",
            content_hash="hash_series2",
            part_count=1,
            series_json=json.dumps(parts),
        )
        db_session.add(series_story)
        db_session.commit()
        db_session.refresh(submitted)
        db_session.refresh(series_story)

        resp = client.get(f"/stories/{series_story.id}/series-parts")
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["story_id"] == submitted.id

    def test_enriches_part_with_host_variant(self, client, db_session):
        """URL matching handles www vs non-www host variants."""
        import json
        # DB has www.reddit.com URL
        submitted = Story(
            title="Part 1",
            reddit_url="https://www.reddit.com/r/nosleep/comments/part1/part_one/",
            text_content="Content.",
            narration_text="Content.",
            content_hash="hash_host",
            part_count=1,
        )
        db_session.add(submitted)

        # Part URL uses reddit.com (no www)
        parts = [{"title": "Part 1", "url": "https://reddit.com/r/nosleep/comments/part1/part_one/"}]
        series_story = Story(
            title="Series",
            reddit_url="https://www.reddit.com/r/nosleep/comments/s/series2/",
            text_content="Series.",
            narration_text="Series.",
            content_hash="hash_series3",
            part_count=1,
            series_json=json.dumps(parts),
        )
        db_session.add(series_story)
        db_session.commit()
        db_session.refresh(submitted)
        db_session.refresh(series_story)

        resp = client.get(f"/stories/{series_story.id}/series-parts")
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["story_id"] == submitted.id



    @patch("app.routers.stories.fetch_post_metadata")
    @patch("app.routers.stories.fetch_story_text")
    def test_returns_first_part_only(self, mock_text, mock_metadata, client, auth_headers, db_session):
        """Preview fetches only the first part's text, not the full multi-part chain."""
        mock_metadata.return_value = {"title": "Scary Title", "author": "ghost"}
        mock_text.return_value = "Part one text."

        resp = client.get("/stories/fetch-preview", params={
            "reddit_url": "https://www.reddit.com/r/nosleep/comments/abc/scary_title/"
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Scary Title"
        assert data["author"] == "ghost"
        assert data["text"] == "Part one text."
        mock_text.assert_called_once()

    def test_requires_auth(self, client, db_session):
        resp = client.get("/stories/fetch-preview", params={
            "reddit_url": "https://www.reddit.com/r/nosleep/comments/abc/story/"
        })
        assert resp.status_code == 401

    def test_rate_limited_after_30_requests(self, client, auth_headers, db_session):
        """31st request within 60 seconds returns 429."""
        with patch("app.routers.stories.fetch_post_metadata") as mock_meta, \
             patch("app.routers.stories.fetch_story_text") as mock_text:
            mock_meta.return_value = {"title": "T", "author": "A"}
            mock_text.return_value = "text"
            url = "https://www.reddit.com/r/nosleep/comments/abc/story/"
            for _ in range(30):
                resp = client.get("/stories/fetch-preview", params={"reddit_url": url},
                                  headers=auth_headers)
                assert resp.status_code == 200
            resp = client.get("/stories/fetch-preview", params={"reddit_url": url},
                              headers=auth_headers)
            assert resp.status_code == 429

    def test_rejects_non_reddit_url(self, client, auth_headers, db_session):
        resp = client.get("/stories/fetch-preview", params={
            "reddit_url": "https://evil.com/r/nosleep/comments/abc/story/"
        }, headers=auth_headers)
        assert resp.status_code == 400


class TestPlaybackState:
    def test_save_playback_position(self, client, sample_story, auth_headers, db_session):
        resp = client.post("/stories/playback", json={
            "story_id": sample_story.id,
            "position_seconds": 45.5,
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["story_id"] == sample_story.id
        assert data["position_seconds"] == 45.5

    def test_update_playback_position(self, client, sample_story, auth_headers, db_session):
        # Save initial
        client.post("/stories/playback", json={
            "story_id": sample_story.id,
            "position_seconds": 10.0,
        }, headers=auth_headers)
        # Update
        resp = client.post("/stories/playback", json={
            "story_id": sample_story.id,
            "position_seconds": 90.0,
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["position_seconds"] == 90.0

    def test_get_playback_default(self, client, sample_story, auth_headers, db_session):
        resp = client.get(f"/stories/playback/{sample_story.id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["position_seconds"] == 0.0

    def test_get_playback_saved(self, client, sample_story, auth_headers, db_session):
        client.post("/stories/playback", json={
            "story_id": sample_story.id,
            "position_seconds": 120.5,
        }, headers=auth_headers)
        resp = client.get(f"/stories/playback/{sample_story.id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["position_seconds"] == 120.5

    def test_save_playback_nonexistent_story(self, client, auth_headers, db_session):
        resp = client.post("/stories/playback", json={
            "story_id": 9999,
            "position_seconds": 10.0,
        }, headers=auth_headers)
        assert resp.status_code == 404

    def test_anonymous_save_returns_zero(self, client, sample_story, db_session):
        """Anonymous users get a zero-position response without saving."""
        resp = client.post("/stories/playback", json={
            "story_id": sample_story.id,
            "position_seconds": 45.5,
        })
        assert resp.status_code == 200
        assert resp.json()["position_seconds"] == 0.0

    def test_anonymous_get_returns_zero(self, client, sample_story, db_session):
        """Anonymous users always get zero position."""
        resp = client.get(f"/stories/playback/{sample_story.id}")
        assert resp.status_code == 200
        assert resp.json()["position_seconds"] == 0.0

    def test_per_user_isolation(self, client, sample_story, db_session):
        """Two different users have independent playback positions."""
        from app.auth import hash_password, create_access_token

        # Create a second user
        user2 = User(
            username="otheruser",
            password_hash=hash_password("otherpass"),
            is_admin=False,
        )
        db_session.add(user2)
        db_session.commit()
        db_session.refresh(user2)

        # First user (from test_user fixture via auth_headers)
        user1 = User(
            username="user1",
            password_hash=hash_password("pass1"),
            is_admin=False,
        )
        db_session.add(user1)
        db_session.commit()
        db_session.refresh(user1)

        headers1 = {"Authorization": f"Bearer {create_access_token(user1.id, user1.username)}"}
        headers2 = {"Authorization": f"Bearer {create_access_token(user2.id, user2.username)}"}

        # User 1 saves at 30s
        client.post("/stories/playback", json={
            "story_id": sample_story.id,
            "position_seconds": 30.0,
        }, headers=headers1)

        # User 2 saves at 120s
        client.post("/stories/playback", json={
            "story_id": sample_story.id,
            "position_seconds": 120.0,
        }, headers=headers2)

        # Each user sees their own position
        resp1 = client.get(f"/stories/playback/{sample_story.id}", headers=headers1)
        assert resp1.json()["position_seconds"] == 30.0

        resp2 = client.get(f"/stories/playback/{sample_story.id}", headers=headers2)
        assert resp2.json()["position_seconds"] == 120.0
