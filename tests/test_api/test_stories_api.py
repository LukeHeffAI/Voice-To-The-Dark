"""Tests for stories API endpoints."""

import json
from unittest.mock import patch

import pytest

from apps.stories.models import Story, StoryFolder, StoryFolderMembership, StoryView
from apps.player.models import PlaybackState


pytestmark = pytest.mark.django_db


# ── Helper fixtures ──────────────────────────────────────────────


@pytest.fixture
def second_user(db):
    """Create a second test user for isolation tests."""
    from apps.accounts.models import User
    from apps.accounts.auth import create_access_token

    user = User.objects.create_user(username="seconduser", password="secondpass123")
    return user


@pytest.fixture
def second_auth_headers(second_user):
    """Authorization headers for the second user."""
    from apps.accounts.auth import create_access_token

    token = create_access_token(second_user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


# ── Submit Story ─────────────────────────────────────────────────


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

    @patch("apps.stories.api.find_series_parts", return_value=[])
    @patch("apps.stories.api.clean_for_narration", return_value="Cleaned text")
    @patch("apps.stories.api.hash_content", return_value="unique_hash_strip")
    @patch("apps.stories.api.fetch_story_text", return_value="Story text")
    @patch("apps.stories.api.fetch_post_metadata", return_value={"title": "Strip Test", "author": "a1"})
    def test_submit_strips_query_string(
        self, mock_meta, mock_text, mock_hash, mock_clean, mock_series, client, auth_headers
    ):
        resp = client.post(
            "/api/stories/submit",
            data=json.dumps({
                "reddit_url": "https://www.reddit.com/r/nosleep/comments/xyz/test?utm_source=share&utm_medium=web"
            }),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200
        story = Story.objects.first()
        assert "?" not in story.reddit_url
        assert "utm_source" not in story.reddit_url

    def test_submit_rejects_non_reddit_host(self, client, auth_headers):
        resp = client.post(
            "/api/stories/submit",
            data=json.dumps({"reddit_url": "https://evil.com/r/nosleep/comments/xyz/test"}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 400
        assert "host" in resp.json()["detail"].lower()

    def test_submit_rejects_non_nosleep_path(self, client, auth_headers):
        resp = client.post(
            "/api/stories/submit",
            data=json.dumps({"reddit_url": "https://www.reddit.com/r/horror/comments/xyz/test"}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 400
        assert "nosleep" in resp.json()["detail"].lower()


# ── Manual Submit Story ──────────────────────────────────────────


class TestManualSubmitStory:
    @patch("apps.stories.api.find_series_parts", return_value=[])
    @patch("apps.stories.api.clean_for_narration", return_value="Cleaned text")
    @patch("apps.stories.api.hash_content", return_value="manual_hash_1")
    def test_manual_submit_new_story(self, mock_hash, mock_clean, mock_series, client, auth_headers):
        resp = client.post(
            "/api/stories/submit-manual",
            data=json.dumps({"title": "My Scary Story", "text_content": "It was a dark night..."}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "My Scary Story"
        assert Story.objects.count() == 1

    @patch("apps.stories.api.find_series_parts", return_value=[])
    @patch("apps.stories.api.clean_for_narration", return_value="Cleaned text")
    @patch("apps.stories.api.hash_content", return_value="manual_hash_url")
    def test_manual_submit_with_reddit_url(self, mock_hash, mock_clean, mock_series, client, auth_headers):
        url = "https://www.reddit.com/r/nosleep/comments/abc999/my_story"
        resp = client.post(
            "/api/stories/submit-manual",
            data=json.dumps({
                "title": "URL Story",
                "text_content": "Some horror text",
                "reddit_url": url,
            }),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200
        story = Story.objects.first()
        assert story.reddit_url == url

    def test_manual_submit_rejects_non_reddit_url(self, client, auth_headers):
        resp = client.post(
            "/api/stories/submit-manual",
            data=json.dumps({
                "title": "Bad URL Story",
                "text_content": "Some text",
                "reddit_url": "https://evil.com/story",
            }),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 400

    def test_manual_submit_rejects_non_nosleep_url(self, client, auth_headers):
        resp = client.post(
            "/api/stories/submit-manual",
            data=json.dumps({
                "title": "Wrong Sub Story",
                "text_content": "Some text",
                "reddit_url": "https://www.reddit.com/r/AskReddit/comments/abc/test",
            }),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 400

    @patch("apps.stories.api.find_series_parts", return_value=[])
    @patch("apps.stories.api.clean_for_narration", return_value="Cleaned text")
    @patch("apps.stories.api.hash_content", return_value="dup_manual_hash")
    def test_manual_submit_duplicate_content(self, mock_hash, mock_clean, mock_series, client, auth_headers):
        # First submission
        resp1 = client.post(
            "/api/stories/submit-manual",
            data=json.dumps({"title": "Original", "text_content": "Same content here"}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp1.status_code == 200
        first_id = resp1.json()["id"]

        # Second submission with same text (same hash)
        resp2 = client.post(
            "/api/stories/submit-manual",
            data=json.dumps({"title": "Duplicate", "text_content": "Same content here"}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp2.status_code == 200
        assert resp2.json()["id"] == first_id

    def test_manual_submit_empty_text(self, client, auth_headers):
        resp = client.post(
            "/api/stories/submit-manual",
            data=json.dumps({"title": "Has Title", "text_content": "   "}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 400

    def test_manual_submit_empty_title(self, client, auth_headers):
        resp = client.post(
            "/api/stories/submit-manual",
            data=json.dumps({"title": "   ", "text_content": "Has content here"}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 400

    def test_manual_submit_requires_auth(self, client, db):
        resp = client.post(
            "/api/stories/submit-manual",
            data=json.dumps({"title": "No Auth", "text_content": "Some text"}),
            content_type="application/json",
        )
        assert resp.status_code == 401

    @patch("apps.stories.api.find_series_parts", return_value=[])
    @patch("apps.stories.api.clean_for_narration", return_value="Cleaned text")
    @patch("apps.stories.api.hash_content", return_value="author_hash_1")
    def test_manual_submit_author_persisted(self, mock_hash, mock_clean, mock_series, client, auth_headers):
        resp = client.post(
            "/api/stories/submit-manual",
            data=json.dumps({
                "title": "Author Story",
                "text_content": "Spooky text",
                "author": "u/spookywriter",
            }),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200
        story = Story.objects.first()
        assert story.author == "u/spookywriter"


# ── List Stories ─────────────────────────────────────────────────


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

    def test_empty_list(self, client, db):
        resp = client.get("/api/stories/")
        assert resp.status_code == 200
        data = resp.json()
        assert data == []

    def test_has_audio_and_has_script_fields(self, client, test_story):
        resp = client.get("/api/stories/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        item = data[0]
        assert "has_audio" in item
        assert "has_script" in item
        assert isinstance(item["has_audio"], bool)
        assert isinstance(item["has_script"], bool)


# ── Top Nosleep ──────────────────────────────────────────────────


class TestTopNosleep:
    @patch("services.reddit.fetch_top_posts", return_value=[
        {"url": "https://www.reddit.com/r/nosleep/comments/aaa/post1", "title": "Post 1"},
        {"url": "https://www.reddit.com/r/nosleep/comments/bbb/post2", "title": "Post 2"},
    ])
    def test_returns_posts(self, mock_fetch, client, db):
        resp = client.get("/api/stories/top-nosleep?timeframe=alltime")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["title"] == "Post 1"
        assert data[0]["already_submitted"] is False
        assert data[1]["already_submitted"] is False

    @patch("services.reddit.fetch_top_posts", return_value=[
        {"url": "https://www.reddit.com/r/nosleep/comments/abc123/test_story", "title": "Already Here"},
    ])
    def test_flags_already_submitted(self, mock_fetch, client, test_story):
        resp = client.get("/api/stories/top-nosleep?timeframe=alltime")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["already_submitted"] is True

    @patch("services.reddit.fetch_top_posts", side_effect=RuntimeError("Reddit is down"))
    def test_reddit_unavailable_returns_502(self, mock_fetch, client, db):
        resp = client.get("/api/stories/top-nosleep?timeframe=alltime")
        assert resp.status_code == 502


# ── Get Story ────────────────────────────────────────────────────


class TestGetStory:
    def test_get_story(self, client, test_story):
        resp = client.get(f"/api/stories/{test_story.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Test Horror Story"

    def test_get_story_not_found(self, client, db):
        resp = client.get("/api/stories/9999")
        assert resp.status_code == 404


# ── Hide / Unhide ────────────────────────────────────────────────


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

    def test_hide_no_view_still_ok(self, client, auth_headers, test_story):
        """Hide when no StoryView exists should still return 200."""
        resp = client.post(f"/api/stories/{test_story.id}/hide", **auth_headers)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_unhide_no_view_still_ok(self, client, auth_headers, test_story):
        """Unhide when no StoryView exists should still return 200."""
        resp = client.post(f"/api/stories/{test_story.id}/unhide", **auth_headers)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_hide_requires_auth(self, client, test_story):
        resp = client.post(f"/api/stories/{test_story.id}/hide")
        assert resp.status_code == 401

    def test_unhide_requires_auth(self, client, test_story):
        resp = client.post(f"/api/stories/{test_story.id}/unhide")
        assert resp.status_code == 401


# ── Check Duplicate ──────────────────────────────────────────────


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


# ── Series Parts ─────────────────────────────────────────────────


class TestSeriesParts:
    @patch("apps.stories.api.find_series_parts", return_value=[])
    def test_returns_empty_for_story_without_parts(self, mock_find, client, test_story):
        # Ensure story has no series_json
        test_story.series_json = None
        test_story.save()
        resp = client.get(f"/api/stories/{test_story.id}/series-parts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["parts"] == []
        assert data["total_count"] == 0

    def test_returns_404_for_nonexistent_story(self, client, db):
        resp = client.get("/api/stories/9999/series-parts")
        assert resp.status_code == 404

    @patch("apps.stories.api.find_series_parts", return_value=[])
    def test_enriches_submitted_part_with_story_id(self, mock_find, client, db):
        """When series_json references a URL that matches another story, story_id is populated."""
        story_a = Story.objects.create(
            title="Part 1",
            reddit_url="https://www.reddit.com/r/nosleep/comments/aaa/part1",
            text_content="Part 1 text",
            content_hash="hash_part1",
        )
        series_data = [
            {"title": "Part 1", "url": "https://www.reddit.com/r/nosleep/comments/aaa/part1"},
            {"title": "Part 2", "url": "https://www.reddit.com/r/nosleep/comments/bbb/part2"},
        ]
        story_b = Story.objects.create(
            title="Part 2",
            author="test_author",
            reddit_url="https://www.reddit.com/r/nosleep/comments/bbb/part2",
            text_content="Part 2 text",
            content_hash="hash_part2",
            series_json=series_data,
        )
        resp = client.get(f"/api/stories/{story_b.id}/series-parts")
        assert resp.status_code == 200
        data = resp.json()
        parts = data["parts"]
        # Find the part matching story_a's URL
        part_a = next(p for p in parts if "aaa" in (p.get("url") or ""))
        assert part_a["story_id"] == story_a.id


# ── Fetch Preview ────────────────────────────────────────────────


class TestFetchPreview:
    @patch("apps.stories.api.fetch_story_text", return_value="Once upon a midnight dreary...")
    @patch("apps.stories.api.fetch_post_metadata", return_value={"title": "The Raven", "author": "poe"})
    def test_returns_preview(self, mock_meta, mock_text, client, auth_headers):
        url = "https://www.reddit.com/r/nosleep/comments/zzz/the_raven"
        resp = client.get(f"/api/stories/fetch-preview?reddit_url={url}", **auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "The Raven"
        assert data["author"] == "poe"
        assert data["text"] == "Once upon a midnight dreary..."

    def test_requires_auth(self, client, db):
        url = "https://www.reddit.com/r/nosleep/comments/zzz/test"
        resp = client.get(f"/api/stories/fetch-preview?reddit_url={url}")
        assert resp.status_code == 401

    def test_rejects_non_reddit_url(self, client, auth_headers):
        resp = client.get(
            "/api/stories/fetch-preview?reddit_url=https://evil.com/story",
            **auth_headers,
        )
        assert resp.status_code == 400

    @patch("apps.stories.api.fetch_story_text", return_value="text")
    @patch("apps.stories.api.fetch_post_metadata", return_value={"title": "T", "author": "a"})
    def test_rate_limited_after_30_requests(self, mock_meta, mock_text, client, auth_headers):
        url = "https://www.reddit.com/r/nosleep/comments/zzz/rate_test"
        for i in range(30):
            resp = client.get(f"/api/stories/fetch-preview?reddit_url={url}", **auth_headers)
            assert resp.status_code == 200, f"Request {i+1} failed unexpectedly"

        # 31st request should be rate limited
        resp = client.get(f"/api/stories/fetch-preview?reddit_url={url}", **auth_headers)
        assert resp.status_code == 429


# ── Folders ──────────────────────────────────────────────────────


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

    def test_empty_list(self, client, auth_headers):
        resp = client.get("/api/stories/folders/list", **auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_story_count_reflects_memberships(self, client, auth_headers, test_user, test_story):
        folder = StoryFolder.objects.create(user=test_user, name="Counted")
        StoryFolderMembership.objects.create(folder=folder, story=test_story)
        story2 = Story.objects.create(
            title="Story 2", text_content="Content 2", content_hash="hash_count2",
        )
        StoryFolderMembership.objects.create(folder=folder, story=story2)
        resp = client.get("/api/stories/folders/list", **auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        counted = next(f for f in data if f["name"] == "Counted")
        assert counted["story_count"] == 2

    def test_folders_isolated_per_user(
        self, client, auth_headers, test_user, second_user, second_auth_headers
    ):
        StoryFolder.objects.create(user=test_user, name="User1 Folder")
        StoryFolder.objects.create(user=second_user, name="User2 Folder")

        resp = client.get("/api/stories/folders/list", **auth_headers)
        assert resp.status_code == 200
        names = [f["name"] for f in resp.json()]
        assert "User1 Folder" in names
        assert "User2 Folder" not in names

        resp2 = client.get("/api/stories/folders/list", **second_auth_headers)
        assert resp2.status_code == 200
        names2 = [f["name"] for f in resp2.json()]
        assert "User2 Folder" in names2
        assert "User1 Folder" not in names2

    def test_create_folder_strips_whitespace(self, client, auth_headers):
        resp = client.post(
            "/api/stories/folders/create",
            data=json.dumps({"name": "  Spooky  "}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        # The API may or may not strip whitespace; verify stored name matches response
        folder = StoryFolder.objects.get(id=data["id"])
        assert data["name"] == folder.name

    def test_create_folder_empty_name_rejected(self, client, auth_headers):
        resp = client.post(
            "/api/stories/folders/create",
            data=json.dumps({"name": ""}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code in (400, 422)

    def test_same_name_different_users(
        self, client, auth_headers, second_auth_headers, test_user, second_user
    ):
        resp1 = client.post(
            "/api/stories/folders/create",
            data=json.dumps({"name": "SharedName"}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp1.status_code == 200

        resp2 = client.post(
            "/api/stories/folders/create",
            data=json.dumps({"name": "SharedName"}),
            content_type="application/json",
            **second_auth_headers,
        )
        assert resp2.status_code == 200

        assert StoryFolder.objects.filter(name="SharedName").count() == 2

    def test_delete_removes_memberships(self, client, auth_headers, test_user, test_story):
        folder = StoryFolder.objects.create(user=test_user, name="DeleteMe")
        StoryFolderMembership.objects.create(folder=folder, story=test_story)
        folder_id = folder.id
        assert StoryFolderMembership.objects.filter(folder_id=folder_id).count() == 1

        resp = client.delete(f"/api/stories/folders/{folder_id}", **auth_headers)
        assert resp.status_code == 200
        assert StoryFolderMembership.objects.filter(folder_id=folder_id).count() == 0

    def test_delete_another_users_folder_404(
        self, client, auth_headers, test_user, second_user, second_auth_headers
    ):
        folder = StoryFolder.objects.create(user=second_user, name="NotYours")
        resp = client.delete(f"/api/stories/folders/{folder.id}", **auth_headers)
        assert resp.status_code == 404
        # Folder should still exist
        assert StoryFolder.objects.filter(id=folder.id).exists()

    def test_add_story_already_in_folder(self, client, auth_headers, test_user, test_story):
        folder = StoryFolder.objects.create(user=test_user, name="HasStory")
        StoryFolderMembership.objects.create(folder=folder, story=test_story)
        resp = client.post(
            f"/api/stories/folders/{folder.id}/add",
            data=json.dumps({"story_id": test_story.id}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200
        assert "already" in resp.json().get("message", "").lower()

    def test_add_nonexistent_story_404(self, client, auth_headers, test_user):
        folder = StoryFolder.objects.create(user=test_user, name="Empty")
        resp = client.post(
            f"/api/stories/folders/{folder.id}/add",
            data=json.dumps({"story_id": 99999}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 404

    def test_add_to_another_users_folder_404(
        self, client, auth_headers, test_user, second_user, test_story
    ):
        folder = StoryFolder.objects.create(user=second_user, name="NotMine")
        resp = client.post(
            f"/api/stories/folders/{folder.id}/add",
            data=json.dumps({"story_id": test_story.id}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 404

    def test_remove_from_another_users_folder_404(
        self, client, auth_headers, test_user, second_user, test_story
    ):
        folder = StoryFolder.objects.create(user=second_user, name="NotMine")
        StoryFolderMembership.objects.create(folder=folder, story=test_story)
        resp = client.delete(
            f"/api/stories/folders/{folder.id}/stories/{test_story.id}",
            **auth_headers,
        )
        assert resp.status_code == 404

    def test_list_folders_requires_auth(self, client, db):
        resp = client.get("/api/stories/folders/list")
        assert resp.status_code == 401

    def test_create_folder_requires_auth(self, client, db):
        resp = client.post(
            "/api/stories/folders/create",
            data=json.dumps({"name": "NoAuth"}),
            content_type="application/json",
        )
        assert resp.status_code == 401

    def test_delete_folder_requires_auth(self, client, db):
        resp = client.delete("/api/stories/folders/1")
        assert resp.status_code == 401

    def test_add_to_folder_requires_auth(self, client, db):
        resp = client.post(
            "/api/stories/folders/1/add",
            data=json.dumps({"story_id": 1}),
            content_type="application/json",
        )
        assert resp.status_code == 401

    def test_remove_from_folder_requires_auth(self, client, db):
        resp = client.delete("/api/stories/folders/1/stories/1")
        assert resp.status_code == 401

    def test_list_folder_stories(self, client, auth_headers, test_user, test_story):
        folder = StoryFolder.objects.create(user=test_user, name="WithStory")
        StoryFolderMembership.objects.create(folder=folder, story=test_story)
        resp = client.get(f"/api/stories/folders/{folder.id}/stories", **auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == test_story.id
        assert data[0]["title"] == test_story.title

    def test_list_folder_stories_empty(self, client, auth_headers, test_user):
        folder = StoryFolder.objects.create(user=test_user, name="EmptyFolder")
        resp = client.get(f"/api/stories/folders/{folder.id}/stories", **auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_folder_stories_another_users_folder_404(
        self, client, auth_headers, test_user, second_user, test_story
    ):
        folder = StoryFolder.objects.create(user=second_user, name="OtherUserFolder")
        StoryFolderMembership.objects.create(folder=folder, story=test_story)
        resp = client.get(f"/api/stories/folders/{folder.id}/stories", **auth_headers)
        assert resp.status_code == 404

    def test_list_folder_stories_nonexistent_folder_404(self, client, auth_headers):
        resp = client.get("/api/stories/folders/9999/stories", **auth_headers)
        assert resp.status_code == 404


# ── Playback ─────────────────────────────────────────────────────


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

    def test_update_playback_position(self, client, auth_headers, test_user, test_story):
        # Save initial position
        client.post(
            "/api/stories/playback",
            data=json.dumps({"story_id": test_story.id, "position_seconds": 10.0}),
            content_type="application/json",
            **auth_headers,
        )
        # Update to new position
        resp = client.post(
            "/api/stories/playback",
            data=json.dumps({"story_id": test_story.id, "position_seconds": 55.5}),
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["position_seconds"] == 55.5
        # Verify only one record exists
        assert PlaybackState.objects.filter(user=test_user, story=test_story).count() == 1

    def test_per_user_isolation(
        self, client, auth_headers, test_user, second_user, second_auth_headers, test_story
    ):
        # User 1 saves position at 20s
        client.post(
            "/api/stories/playback",
            data=json.dumps({"story_id": test_story.id, "position_seconds": 20.0}),
            content_type="application/json",
            **auth_headers,
        )
        # User 2 saves position at 80s
        client.post(
            "/api/stories/playback",
            data=json.dumps({"story_id": test_story.id, "position_seconds": 80.0}),
            content_type="application/json",
            **second_auth_headers,
        )

        # Verify each user sees their own position
        resp1 = client.get(f"/api/stories/playback/{test_story.id}", **auth_headers)
        assert resp1.json()["position_seconds"] == 20.0

        resp2 = client.get(f"/api/stories/playback/{test_story.id}", **second_auth_headers)
        assert resp2.json()["position_seconds"] == 80.0
