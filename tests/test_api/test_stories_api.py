"""Tests for stories API endpoints."""

import json
from unittest.mock import patch

import pytest

from apps.stories.models import Story, StoryFolder, StoryFolderMembership, StoryView
from apps.player.models import PlaybackState


pytestmark = pytest.mark.django_db


class TestSubmitStory:
    @patch("apps.stories.api.find_series_parts", return_value=[])
    @patch("apps.stories.api.clean_for_narration", return_value="Cleaned text")
    @patch("apps.stories.api.hash_content", return_value="unique_hash_1")
    @patch("apps.stories.api.fetch_story_text", return_value="Story text content")
    @patch("apps.stories.api.fetch_post_metadata", return_value={"title": "Scary Story", "author": "author1"})
    def test_submit_story(self, mock_meta, mock_text, mock_hash, mock_clean, mock_series, client, auth_headers):
        resp = client.post(
            "/api/stories/submit",
            data=json.dumps({"reddit_url": "https://www.reddit.com/r/nosleep/comments/xyz/test"}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Scary Story"
        assert Story.objects.count() == 1

    def test_submit_story_unauthenticated(self, client, db):
        resp = client.post(
            "/api/stories/submit",
            data=json.dumps({"reddit_url": "https://www.reddit.com/r/nosleep/comments/xyz/test"}),
            content_type="application/json",
        )
        assert resp.status_code == 401

    def test_submit_story_returns_existing(self, client, auth_headers, test_story):
        resp = client.post(
            "/api/stories/submit",
            data=json.dumps({"reddit_url": test_story.reddit_url}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == test_story.id

    def test_submit_invalid_url(self, client, auth_headers):
        resp = client.post(
            "/api/stories/submit",
            data=json.dumps({"reddit_url": "https://example.com/not-reddit"}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 400


class TestListStories:
    def test_list_stories(self, client, test_story):
        resp = client.get("/api/stories/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Test Horror Story"
        assert "has_audio" in data[0]

    def test_list_stories_pagination(self, client, db):
        for i in range(5):
            Story.objects.create(
                title=f"Story {i}",
                text_content=f"Content {i}",
                content_hash=f"hash{i}",
            )
        resp = client.get("/api/stories/?skip=0&limit=3")
        assert resp.status_code == 200
        assert len(resp.json()) == 3


class TestGetStory:
    def test_get_story(self, client, test_story):
        resp = client.get(f"/api/stories/{test_story.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Test Horror Story"

    def test_get_story_not_found(self, client, db):
        resp = client.get("/api/stories/9999")
        assert resp.status_code == 404


class TestHideUnhide:
    def test_hide_story(self, client, auth_headers, test_user, test_story):
        StoryView.objects.create(user=test_user, story=test_story)
        resp = client.post(f"/api/stories/{test_story.id}/hide", **auth_headers)
        assert resp.status_code == 200
        view = StoryView.objects.get(user=test_user, story=test_story)
        assert view.hidden is True

    def test_unhide_story(self, client, auth_headers, test_user, test_story):
        StoryView.objects.create(user=test_user, story=test_story, hidden=True)
        resp = client.post(f"/api/stories/{test_story.id}/unhide", **auth_headers)
        assert resp.status_code == 200
        view = StoryView.objects.get(user=test_user, story=test_story)
        assert view.hidden is False


class TestCheckDuplicate:
    def test_check_duplicate_exists(self, client, test_story):
        resp = client.get(f"/api/stories/check-duplicate/?reddit_url={test_story.reddit_url}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_duplicate"] is True
        assert data["existing_story_id"] == test_story.id

    def test_check_duplicate_not_found(self, client, db):
        resp = client.get("/api/stories/check-duplicate/?reddit_url=https://example.com/unique")
        assert resp.status_code == 200
        assert resp.json()["is_duplicate"] is False


class TestFolders:
    def test_create_folder(self, client, auth_headers):
        resp = client.post(
            "/api/stories/folders/create",
            data=json.dumps({"name": "Favorites"}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Favorites"
        assert data["story_count"] == 0

    def test_list_folders(self, client, auth_headers, test_user):
        StoryFolder.objects.create(user=test_user, name="Folder A")
        StoryFolder.objects.create(user=test_user, name="Folder B")
        resp = client.get("/api/stories/folders/list", **auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_delete_folder(self, client, auth_headers, test_user):
        folder = StoryFolder.objects.create(user=test_user, name="ToDelete")
        resp = client.delete(f"/api/stories/folders/{folder.id}", **auth_headers)
        assert resp.status_code == 200
        assert not StoryFolder.objects.filter(id=folder.id).exists()

    def test_delete_folder_not_found(self, client, auth_headers):
        resp = client.delete("/api/stories/folders/9999", **auth_headers)
        assert resp.status_code == 404

    def test_add_story_to_folder(self, client, auth_headers, test_user, test_story):
        folder = StoryFolder.objects.create(user=test_user, name="MyFolder")
        resp = client.post(
            f"/api/stories/folders/{folder.id}/add",
            data=json.dumps({"story_id": test_story.id}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200
        assert StoryFolderMembership.objects.filter(folder=folder, story=test_story).exists()

    def test_remove_story_from_folder(self, client, auth_headers, test_user, test_story):
        folder = StoryFolder.objects.create(user=test_user, name="MyFolder")
        StoryFolderMembership.objects.create(folder=folder, story=test_story)
        resp = client.delete(
            f"/api/stories/folders/{folder.id}/stories/{test_story.id}",
            **auth_headers,
        )
        assert resp.status_code == 200
        assert not StoryFolderMembership.objects.filter(folder=folder, story=test_story).exists()

    def test_create_duplicate_folder(self, client, auth_headers, test_user):
        StoryFolder.objects.create(user=test_user, name="Existing")
        resp = client.post(
            "/api/stories/folders/create",
            data=json.dumps({"name": "Existing"}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 409


class TestPlayback:
    def test_save_playback_position(self, client, auth_headers, test_user, test_story):
        resp = client.post(
            "/api/stories/playback",
            data=json.dumps({"story_id": test_story.id, "position_seconds": 42.5}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["position_seconds"] == 42.5

    def test_get_playback_position(self, client, auth_headers, test_user, test_story):
        PlaybackState.objects.create(user=test_user, story=test_story, position_seconds=30.0)
        resp = client.get(f"/api/stories/playback/{test_story.id}", **auth_headers)
        assert resp.status_code == 200
        assert resp.json()["position_seconds"] == 30.0

    def test_get_playback_position_anonymous(self, client, test_story):
        resp = client.get(f"/api/stories/playback/{test_story.id}")
        assert resp.status_code == 200
        assert resp.json()["position_seconds"] == 0.0

    def test_save_playback_anonymous(self, client, test_story):
        resp = client.post(
            "/api/stories/playback",
            data=json.dumps({"story_id": test_story.id, "position_seconds": 10.0}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.json()["position_seconds"] == 0.0

    def test_save_playback_story_not_found(self, client, auth_headers):
        resp = client.post(
            "/api/stories/playback",
            data=json.dumps({"story_id": 9999, "position_seconds": 10.0}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 404
