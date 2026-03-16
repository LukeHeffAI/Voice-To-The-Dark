"""Tests for the stories API endpoints (/api/stories/)."""

import pytest
from unittest.mock import patch

from apps.accounts.auth import create_access_token
from apps.accounts.models import User
from apps.core.rate_limit import _request_log
from apps.player.models import PlaybackState
from apps.stories.models import Story, StoryFolder, StoryFolderMembership, StoryView

from tests.conftest import post_json


# ── Helpers ──────────────────────────────────────────────────────────

VALID_REDDIT_URL = "https://www.reddit.com/r/nosleep/comments/abc123/the_haunted_house/"
VALID_REDDIT_URL_2 = "https://www.reddit.com/r/nosleep/comments/xyz789/another_story/"


def _make_story(db, **overrides):
    """Create a Story with sensible defaults, overridden by kwargs."""
    defaults = dict(
        title="Default Story",
        reddit_url=VALID_REDDIT_URL,
        text_content="Some text content.",
        narration_text="Some narration text.",
        content_hash="defaulthash000",
        part_count=1,
    )
    defaults.update(overrides)
    return Story.objects.create(**defaults)


# ── 1. TestListStories ───────────────────────────────────────────────


@pytest.mark.django_db
class TestListStories:
    def test_empty_list(self, api_client):
        resp = api_client.get("/api/stories/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_stories(self, api_client, sample_story):
        resp = api_client.get("/api/stories/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "The Haunted House"
        assert data[0]["id"] == sample_story.id


# ── 2. TestGetStory ──────────────────────────────────────────────────


@pytest.mark.django_db
class TestGetStory:
    def test_get_existing(self, api_client, sample_story):
        resp = api_client.get(f"/api/stories/{sample_story.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "The Haunted House"
        assert data["id"] == sample_story.id

    def test_get_nonexistent(self, api_client, db):
        resp = api_client.get("/api/stories/99999")
        assert resp.status_code == 404


# ── 3. TestCheckDuplicate ────────────────────────────────────────────


@pytest.mark.django_db
class TestCheckDuplicate:
    def test_no_duplicate(self, api_client, db):
        resp = api_client.get(
            "/api/stories/check-duplicate/?reddit_url=https://www.reddit.com/r/nosleep/comments/zzz/no_match/"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_duplicate"] is False

    def test_finds_duplicate(self, api_client, sample_story):
        resp = api_client.get(
            f"/api/stories/check-duplicate/?reddit_url={sample_story.reddit_url}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_duplicate"] is True
        assert data["existing_story_id"] == sample_story.id


# ── 4. TestTopNosleep ────────────────────────────────────────────────


@pytest.mark.django_db
class TestTopNosleep:
    @patch("apps.stories.api.fetch_top_posts")
    def test_returns_posts(self, mock_fetch, api_client, db):
        mock_fetch.return_value = [
            {"title": "Scary Story", "url": "https://reddit.com/r/nosleep/comments/aaa/scary/"},
        ]
        resp = api_client.get("/api/stories/top-nosleep?timeframe=alltime")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Scary Story"
        assert data[0]["already_submitted"] is False

    @patch("apps.stories.api.fetch_top_posts")
    def test_flags_already_submitted(self, mock_fetch, api_client, sample_story):
        mock_fetch.return_value = [
            {"title": "The Haunted House", "url": sample_story.reddit_url},
        ]
        resp = api_client.get("/api/stories/top-nosleep?timeframe=alltime")
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["already_submitted"] is True

    @patch("apps.stories.api.fetch_top_posts")
    def test_reddit_unavailable_returns_502(self, mock_fetch, api_client, db):
        mock_fetch.side_effect = Exception("Reddit down")
        resp = api_client.get("/api/stories/top-nosleep?timeframe=alltime")
        assert resp.status_code == 502


# ── 5. TestSubmitStory ───────────────────────────────────────────────


@pytest.mark.django_db
class TestSubmitStory:
    @patch("apps.stories.api.find_series_parts", return_value=[])
    @patch("apps.stories.api.fetch_story_text", return_value="This is the story body.")
    @patch("apps.stories.api.fetch_post_metadata", return_value={"title": "New Story", "author": "some_author"})
    def test_submit_new_story(self, mock_meta, mock_text, mock_series, api_client, auth_headers):
        resp = post_json(
            api_client,
            "/api/stories/submit",
            {"reddit_url": VALID_REDDIT_URL},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "New Story"
        assert Story.objects.count() == 1

    @patch("apps.stories.api.find_series_parts", return_value=[])
    @patch("apps.stories.api.fetch_story_text", return_value="Body text here.")
    @patch("apps.stories.api.fetch_post_metadata", return_value={"title": "Stripped", "author": "auth"})
    def test_submit_strips_query_string(self, mock_meta, mock_text, mock_series, api_client, auth_headers):
        url_with_qs = VALID_REDDIT_URL + "?utm_source=share"
        resp = post_json(
            api_client,
            "/api/stories/submit",
            {"reddit_url": url_with_qs},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        story = Story.objects.first()
        assert "?" not in story.reddit_url

    def test_rejects_non_reddit_host(self, api_client, auth_headers):
        resp = post_json(
            api_client,
            "/api/stories/submit",
            {"reddit_url": "https://example.com/r/nosleep/comments/abc/story/"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_rejects_non_nosleep_path(self, api_client, auth_headers):
        resp = post_json(
            api_client,
            "/api/stories/submit",
            {"reddit_url": "https://www.reddit.com/r/askreddit/comments/abc/story/"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    @patch("apps.stories.api.find_series_parts", return_value=[])
    @patch("apps.stories.api.fetch_story_text", return_value="Duplicate body.")
    @patch("apps.stories.api.fetch_post_metadata", return_value={"title": "Dup", "author": "a"})
    def test_submit_returns_existing_on_duplicate_url(self, mock_meta, mock_text, mock_series, api_client, auth_headers, sample_story):
        resp = post_json(
            api_client,
            "/api/stories/submit",
            {"reddit_url": sample_story.reddit_url},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == sample_story.id
        # No new story should have been created
        assert Story.objects.count() == 1

    def test_submit_requires_auth(self, api_client, db):
        resp = post_json(
            api_client,
            "/api/stories/submit",
            {"reddit_url": VALID_REDDIT_URL},
        )
        assert resp.status_code == 401


# ── 6. TestManualSubmitStory ─────────────────────────────────────────


@pytest.mark.django_db
class TestManualSubmitStory:
    @patch("apps.stories.api.find_series_parts", return_value=[])
    def test_manual_submit_new_story(self, mock_series, api_client, auth_headers):
        resp = post_json(
            api_client,
            "/api/stories/submit-manual",
            {"title": "Manual Story", "text_content": "Some manual text."},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Manual Story"
        assert Story.objects.count() == 1

    @patch("apps.stories.api.find_series_parts", return_value=[])
    @patch("apps.stories.api.fetch_story_text", return_value="Fetched text.")
    @patch("apps.stories.api.fetch_post_metadata", return_value={"title": "From Reddit", "author": "redditor"})
    def test_with_reddit_url(self, mock_meta, mock_text, mock_series, api_client, auth_headers):
        resp = post_json(
            api_client,
            "/api/stories/submit-manual",
            {"reddit_url": VALID_REDDIT_URL},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "From Reddit"

    def test_rejects_non_reddit_url(self, api_client, auth_headers):
        resp = post_json(
            api_client,
            "/api/stories/submit-manual",
            {"title": "T", "text_content": "T", "reddit_url": "https://example.com/page"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_rejects_non_nosleep_reddit_url(self, api_client, auth_headers):
        resp = post_json(
            api_client,
            "/api/stories/submit-manual",
            {
                "title": "T",
                "text_content": "T",
                "reddit_url": "https://www.reddit.com/r/askreddit/comments/abc/story/",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 400

    @patch("apps.stories.api.find_series_parts", return_value=[])
    def test_duplicate_content(self, mock_series, api_client, auth_headers, sample_story):
        resp = post_json(
            api_client,
            "/api/stories/submit-manual",
            {
                "title": "Different Title",
                "text_content": sample_story.text_content,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        # Should return the existing story because content hash matches
        assert data["id"] == sample_story.id

    def test_empty_text(self, api_client, auth_headers):
        resp = post_json(
            api_client,
            "/api/stories/submit-manual",
            {"title": "Title Only", "text_content": ""},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_empty_title(self, api_client, auth_headers):
        resp = post_json(
            api_client,
            "/api/stories/submit-manual",
            {"title": "", "text_content": "Some text."},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_requires_auth(self, api_client, db):
        resp = post_json(
            api_client,
            "/api/stories/submit-manual",
            {"title": "No Auth", "text_content": "Text."},
        )
        assert resp.status_code == 401

    @patch("apps.stories.api.find_series_parts", return_value=[])
    def test_author_persisted(self, mock_series, api_client, auth_headers):
        resp = post_json(
            api_client,
            "/api/stories/submit-manual",
            {"title": "Author Test", "text_content": "Body.", "author": "custom_author"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        story = Story.objects.first()
        assert story.author == "custom_author"

    @patch("apps.stories.api.find_series_parts", return_value=[])
    @patch("apps.stories.api.fetch_story_text", return_value="Fetched text.")
    @patch("apps.stories.api.fetch_post_metadata", return_value={"title": "T", "author": "reddit_author"})
    def test_url_author_from_request(self, mock_meta, mock_text, mock_series, api_client, auth_headers):
        """When both URL and explicit author are given, the explicit author wins."""
        resp = post_json(
            api_client,
            "/api/stories/submit-manual",
            {"reddit_url": VALID_REDDIT_URL, "author": "explicit_author"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        story = Story.objects.first()
        assert story.author == "explicit_author"

    @patch("apps.stories.api.find_series_parts", return_value=[])
    @patch("apps.stories.api.fetch_story_text", return_value="Fetched text.")
    @patch("apps.stories.api.fetch_post_metadata", return_value={"title": "T", "author": "reddit_author"})
    def test_url_author_fallback_from_reddit(self, mock_meta, mock_text, mock_series, api_client, auth_headers):
        """When URL is given without explicit author, the Reddit author is used."""
        resp = post_json(
            api_client,
            "/api/stories/submit-manual",
            {"reddit_url": VALID_REDDIT_URL},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        story = Story.objects.first()
        assert story.author == "reddit_author"


# ── 7. TestSeriesParts ───────────────────────────────────────────────


@pytest.mark.django_db
class TestSeriesParts:
    @patch("apps.stories.api.find_series_parts", return_value=[])
    def test_returns_empty_for_story_without_parts(self, mock_find, api_client, sample_story):
        resp = api_client.get(f"/api/stories/{sample_story.id}/series-parts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["parts"] == []
        assert data["total_count"] == 0

    def test_returns_404_for_nonexistent_story(self, api_client, db):
        resp = api_client.get("/api/stories/99999/series-parts")
        assert resp.status_code == 404


# ── 8. TestFetchPreview ──────────────────────────────────────────────


@pytest.mark.django_db
class TestFetchPreview:
    @patch("apps.stories.api.fetch_story_text", return_value="Part one text.")
    @patch("apps.stories.api.fetch_post_metadata", return_value={"title": "Preview Title", "author": "auth"})
    def test_returns_first_part_only(self, mock_meta, mock_text, api_client, auth_headers):
        resp = api_client.get(
            f"/api/stories/fetch-preview?reddit_url={VALID_REDDIT_URL}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Preview Title"
        assert data["text"] == "Part one text."

    def test_requires_auth(self, api_client, db):
        resp = api_client.get(
            f"/api/stories/fetch-preview?reddit_url={VALID_REDDIT_URL}"
        )
        assert resp.status_code == 401

    @patch("apps.stories.api.fetch_story_text", return_value="Text.")
    @patch("apps.stories.api.fetch_post_metadata", return_value={"title": "T", "author": "a"})
    def test_rate_limited_after_30_requests(self, mock_meta, mock_text, api_client, auth_headers, test_user):
        _request_log.clear()
        url = f"/api/stories/fetch-preview?reddit_url={VALID_REDDIT_URL}"
        for _ in range(30):
            resp = api_client.get(url, headers=auth_headers)
            assert resp.status_code == 200

        resp = api_client.get(url, headers=auth_headers)
        assert resp.status_code == 429

    def test_rejects_non_reddit_url(self, api_client, auth_headers):
        resp = api_client.get(
            "/api/stories/fetch-preview?reddit_url=https://example.com/page",
            headers=auth_headers,
        )
        assert resp.status_code == 400


# ── 9. TestPlaybackState ────────────────────────────────────────────


@pytest.mark.django_db
class TestPlaybackState:
    def test_save_playback_position(self, api_client, auth_headers, sample_story):
        resp = post_json(
            api_client,
            "/api/stories/playback",
            {"story_id": sample_story.id, "position_seconds": 42.5},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["position_seconds"] == 42.5
        assert data["story_id"] == sample_story.id

    def test_update_playback_position(self, api_client, auth_headers, sample_story):
        post_json(
            api_client,
            "/api/stories/playback",
            {"story_id": sample_story.id, "position_seconds": 10.0},
            headers=auth_headers,
        )
        resp = post_json(
            api_client,
            "/api/stories/playback",
            {"story_id": sample_story.id, "position_seconds": 99.0},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["position_seconds"] == 99.0
        assert PlaybackState.objects.count() == 1

    def test_get_playback_default(self, api_client, auth_headers, sample_story):
        resp = api_client.get(
            f"/api/stories/playback/{sample_story.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["position_seconds"] == 0.0

    def test_get_playback_saved(self, api_client, auth_headers, sample_story, test_user):
        PlaybackState.objects.create(
            user=test_user, story=sample_story, position_seconds=55.5
        )
        resp = api_client.get(
            f"/api/stories/playback/{sample_story.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["position_seconds"] == 55.5

    def test_save_playback_nonexistent_story(self, api_client, auth_headers):
        resp = post_json(
            api_client,
            "/api/stories/playback",
            {"story_id": 99999, "position_seconds": 10.0},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_anonymous_save_returns_zero(self, api_client, sample_story):
        resp = post_json(
            api_client,
            "/api/stories/playback",
            {"story_id": sample_story.id, "position_seconds": 42.0},
        )
        assert resp.status_code == 200
        assert resp.json()["position_seconds"] == 0.0

    def test_anonymous_get_returns_zero(self, api_client, sample_story):
        resp = api_client.get(f"/api/stories/playback/{sample_story.id}")
        assert resp.status_code == 200
        assert resp.json()["position_seconds"] == 0.0

    def test_per_user_isolation(self, api_client, sample_story, test_user):
        user_b = User.objects.create_user(username="userB", password="pass123")
        headers_a = {"Authorization": f"Bearer {create_access_token(test_user.id, test_user.username)}"}
        headers_b = {"Authorization": f"Bearer {create_access_token(user_b.id, user_b.username)}"}

        post_json(
            api_client,
            "/api/stories/playback",
            {"story_id": sample_story.id, "position_seconds": 100.0},
            headers=headers_a,
        )
        post_json(
            api_client,
            "/api/stories/playback",
            {"story_id": sample_story.id, "position_seconds": 200.0},
            headers=headers_b,
        )

        resp_a = api_client.get(
            f"/api/stories/playback/{sample_story.id}", headers=headers_a
        )
        resp_b = api_client.get(
            f"/api/stories/playback/{sample_story.id}", headers=headers_b
        )
        assert resp_a.json()["position_seconds"] == 100.0
        assert resp_b.json()["position_seconds"] == 200.0


# ── 10. TestHideUnhideStory ─────────────────────────────────────────


@pytest.mark.django_db
class TestHideUnhideStory:
    def test_hide_sets_hidden(self, api_client, auth_headers, sample_story, test_user):
        view = StoryView.objects.create(user=test_user, story=sample_story, hidden=False)
        resp = post_json(
            api_client,
            f"/api/stories/{sample_story.id}/hide",
            {},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        view.refresh_from_db()
        assert view.hidden is True

    def test_hide_no_view_ok(self, api_client, auth_headers, sample_story):
        """Hiding a story that has no StoryView record should succeed silently."""
        resp = post_json(
            api_client,
            f"/api/stories/{sample_story.id}/hide",
            {},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_unhide_clears_hidden(self, api_client, auth_headers, sample_story, test_user):
        view = StoryView.objects.create(user=test_user, story=sample_story, hidden=True)
        resp = post_json(
            api_client,
            f"/api/stories/{sample_story.id}/unhide",
            {},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        view.refresh_from_db()
        assert view.hidden is False

    def test_unhide_no_view_ok(self, api_client, auth_headers, sample_story):
        resp = post_json(
            api_client,
            f"/api/stories/{sample_story.id}/unhide",
            {},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_hide_requires_auth(self, api_client, sample_story):
        resp = post_json(api_client, f"/api/stories/{sample_story.id}/hide", {})
        assert resp.status_code == 401

    def test_unhide_requires_auth(self, api_client, sample_story):
        resp = post_json(api_client, f"/api/stories/{sample_story.id}/unhide", {})
        assert resp.status_code == 401


# ── 11. TestFolders ──────────────────────────────────────────────────


@pytest.mark.django_db
class TestFolders:
    # -- list --

    def test_list_empty(self, api_client, auth_headers):
        resp = api_client.get("/api/stories/folders/list", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_with_folders(self, api_client, auth_headers, test_user):
        StoryFolder.objects.create(user=test_user, name="Favorites")
        resp = api_client.get("/api/stories/folders/list", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Favorites"
        assert data[0]["story_count"] == 0

    def test_list_with_memberships(self, api_client, auth_headers, test_user, sample_story):
        folder = StoryFolder.objects.create(user=test_user, name="My Folder")
        StoryFolderMembership.objects.create(folder=folder, story=sample_story)
        resp = api_client.get("/api/stories/folders/list", headers=auth_headers)
        data = resp.json()
        assert data[0]["story_count"] == 1

    def test_list_requires_auth(self, api_client, db):
        resp = api_client.get("/api/stories/folders/list")
        assert resp.status_code == 401

    def test_list_isolation(self, api_client, auth_headers, test_user):
        other = User.objects.create_user(username="other", password="pass123")
        StoryFolder.objects.create(user=test_user, name="Mine")
        StoryFolder.objects.create(user=other, name="Theirs")
        resp = api_client.get("/api/stories/folders/list", headers=auth_headers)
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Mine"

    # -- create --

    def test_create(self, api_client, auth_headers):
        resp = post_json(
            api_client,
            "/api/stories/folders/create",
            {"name": "New Folder"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Folder"
        assert StoryFolder.objects.count() == 1

    def test_create_strip_whitespace(self, api_client, auth_headers):
        resp = post_json(
            api_client,
            "/api/stories/folders/create",
            {"name": "  Padded  "},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Padded"

    def test_create_empty(self, api_client, auth_headers):
        resp = post_json(
            api_client,
            "/api/stories/folders/create",
            {"name": ""},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_create_duplicate(self, api_client, auth_headers, test_user):
        StoryFolder.objects.create(user=test_user, name="Dups")
        resp = post_json(
            api_client,
            "/api/stories/folders/create",
            {"name": "Dups"},
            headers=auth_headers,
        )
        assert resp.status_code == 409

    def test_create_different_users(self, api_client, auth_headers, test_user):
        other = User.objects.create_user(username="other2", password="pass123")
        StoryFolder.objects.create(user=other, name="Shared Name")
        resp = post_json(
            api_client,
            "/api/stories/folders/create",
            {"name": "Shared Name"},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_create_requires_auth(self, api_client, db):
        resp = post_json(api_client, "/api/stories/folders/create", {"name": "X"})
        assert resp.status_code == 401

    # -- delete --

    def test_delete(self, api_client, auth_headers, test_user):
        folder = StoryFolder.objects.create(user=test_user, name="Delete Me")
        resp = api_client.delete(
            f"/api/stories/folders/{folder.id}", headers=auth_headers
        )
        assert resp.status_code == 200
        assert not StoryFolder.objects.filter(id=folder.id).exists()

    def test_delete_removes_memberships(self, api_client, auth_headers, test_user, sample_story):
        folder = StoryFolder.objects.create(user=test_user, name="Folder")
        StoryFolderMembership.objects.create(folder=folder, story=sample_story)
        api_client.delete(f"/api/stories/folders/{folder.id}", headers=auth_headers)
        assert StoryFolderMembership.objects.count() == 0

    def test_delete_nonexistent(self, api_client, auth_headers):
        resp = api_client.delete(
            "/api/stories/folders/99999", headers=auth_headers
        )
        assert resp.status_code == 404

    def test_delete_another_user(self, api_client, auth_headers, test_user):
        other = User.objects.create_user(username="other3", password="pass123")
        folder = StoryFolder.objects.create(user=other, name="Not Yours")
        resp = api_client.delete(
            f"/api/stories/folders/{folder.id}", headers=auth_headers
        )
        assert resp.status_code == 404

    def test_delete_requires_auth(self, api_client, db):
        resp = api_client.delete("/api/stories/folders/1")
        assert resp.status_code == 401


# ── 12. TestAddStoryToFolder ────────────────────────────────────────


@pytest.mark.django_db
class TestAddStoryToFolder:
    def test_add_story(self, api_client, auth_headers, test_user, sample_story):
        folder = StoryFolder.objects.create(user=test_user, name="Folder")
        resp = post_json(
            api_client,
            f"/api/stories/folders/{folder.id}/add",
            {"story_id": sample_story.id},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert StoryFolderMembership.objects.count() == 1

    def test_already_in_folder(self, api_client, auth_headers, test_user, sample_story):
        folder = StoryFolder.objects.create(user=test_user, name="Folder")
        StoryFolderMembership.objects.create(folder=folder, story=sample_story)
        resp = post_json(
            api_client,
            f"/api/stories/folders/{folder.id}/add",
            {"story_id": sample_story.id},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert StoryFolderMembership.objects.count() == 1

    def test_nonexistent_folder(self, api_client, auth_headers, sample_story):
        resp = post_json(
            api_client,
            "/api/stories/folders/99999/add",
            {"story_id": sample_story.id},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_nonexistent_story(self, api_client, auth_headers, test_user):
        folder = StoryFolder.objects.create(user=test_user, name="Folder")
        resp = post_json(
            api_client,
            f"/api/stories/folders/{folder.id}/add",
            {"story_id": 99999},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_another_users_folder(self, api_client, auth_headers, sample_story):
        other = User.objects.create_user(username="other4", password="pass123")
        folder = StoryFolder.objects.create(user=other, name="Their Folder")
        resp = post_json(
            api_client,
            f"/api/stories/folders/{folder.id}/add",
            {"story_id": sample_story.id},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_requires_auth(self, api_client, sample_story):
        resp = post_json(
            api_client,
            "/api/stories/folders/1/add",
            {"story_id": sample_story.id},
        )
        assert resp.status_code == 401


# ── 13. TestRemoveStoryFromFolder ───────────────────────────────────


@pytest.mark.django_db
class TestRemoveStoryFromFolder:
    def test_remove(self, api_client, auth_headers, test_user, sample_story):
        folder = StoryFolder.objects.create(user=test_user, name="Folder")
        StoryFolderMembership.objects.create(folder=folder, story=sample_story)
        resp = api_client.delete(
            f"/api/stories/folders/{folder.id}/stories/{sample_story.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert StoryFolderMembership.objects.count() == 0

    def test_nonexistent_folder(self, api_client, auth_headers, sample_story):
        resp = api_client.delete(
            f"/api/stories/folders/99999/stories/{sample_story.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_another_users_folder(self, api_client, auth_headers, test_user, sample_story):
        other = User.objects.create_user(username="other5", password="pass123")
        folder = StoryFolder.objects.create(user=other, name="Their Folder")
        StoryFolderMembership.objects.create(folder=folder, story=sample_story)
        resp = api_client.delete(
            f"/api/stories/folders/{folder.id}/stories/{sample_story.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_requires_auth(self, api_client, sample_story):
        resp = api_client.delete(
            f"/api/stories/folders/1/stories/{sample_story.id}"
        )
        assert resp.status_code == 401
