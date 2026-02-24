"""Tests for the /stories router endpoints."""

import pytest
from unittest.mock import patch
from app.models.story import Story, PlaybackState


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


class TestPlaybackState:
    def test_save_playback_position(self, client, sample_story, db_session):
        resp = client.post("/stories/playback", json={
            "story_id": sample_story.id,
            "position_seconds": 45.5,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["story_id"] == sample_story.id
        assert data["position_seconds"] == 45.5

    def test_update_playback_position(self, client, sample_story, db_session):
        # Save initial
        client.post("/stories/playback", json={
            "story_id": sample_story.id,
            "position_seconds": 10.0,
        })
        # Update
        resp = client.post("/stories/playback", json={
            "story_id": sample_story.id,
            "position_seconds": 90.0,
        })
        assert resp.status_code == 200
        assert resp.json()["position_seconds"] == 90.0

    def test_get_playback_default(self, client, sample_story, db_session):
        resp = client.get(f"/stories/playback/{sample_story.id}")
        assert resp.status_code == 200
        assert resp.json()["position_seconds"] == 0.0

    def test_get_playback_saved(self, client, sample_story, db_session):
        client.post("/stories/playback", json={
            "story_id": sample_story.id,
            "position_seconds": 120.5,
        })
        resp = client.get(f"/stories/playback/{sample_story.id}")
        assert resp.status_code == 200
        assert resp.json()["position_seconds"] == 120.5

    def test_save_playback_nonexistent_story(self, client, db_session):
        resp = client.post("/stories/playback", json={
            "story_id": 9999,
            "position_seconds": 10.0,
        })
        assert resp.status_code == 404
