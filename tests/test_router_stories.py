"""Tests for the /stories router endpoints."""

import pytest
from unittest.mock import patch
from app.models.story import Story, PlaybackState, User, StoryView, StoryFolder, StoryFolderMembership


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


class TestFetchPreview:
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


class TestHideUnhideStory:
    def _create_view(self, db_session, user, story, hidden=False):
        view = StoryView(user_id=user.id, story_id=story.id, hidden=hidden)
        db_session.add(view)
        db_session.commit()
        db_session.refresh(view)
        return view

    def test_hide_story_sets_hidden(self, client, sample_story, test_user, auth_headers, db_session):
        self._create_view(db_session, test_user, sample_story, hidden=False)
        resp = client.post(f"/stories/{sample_story.id}/hide", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        view = db_session.query(StoryView).filter(
            StoryView.user_id == test_user.id, StoryView.story_id == sample_story.id
        ).first()
        assert view.hidden is True

    def test_hide_story_no_view_still_returns_ok(self, client, sample_story, auth_headers, db_session):
        resp = client.post(f"/stories/{sample_story.id}/hide", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_unhide_story_clears_hidden(self, client, sample_story, test_user, auth_headers, db_session):
        self._create_view(db_session, test_user, sample_story, hidden=True)
        resp = client.post(f"/stories/{sample_story.id}/unhide", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        view = db_session.query(StoryView).filter(
            StoryView.user_id == test_user.id, StoryView.story_id == sample_story.id
        ).first()
        assert view.hidden is False

    def test_unhide_story_no_view_still_returns_ok(self, client, sample_story, auth_headers, db_session):
        resp = client.post(f"/stories/{sample_story.id}/unhide", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_hide_requires_auth(self, client, sample_story, db_session):
        resp = client.post(f"/stories/{sample_story.id}/hide")
        assert resp.status_code == 401

    def test_unhide_requires_auth(self, client, sample_story, db_session):
        resp = client.post(f"/stories/{sample_story.id}/unhide")
        assert resp.status_code == 401


class TestListFolders:
    def test_empty_list(self, client, auth_headers, db_session):
        resp = client.get("/stories/folders/list", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_user_folders(self, client, test_user, auth_headers, db_session):
        db_session.add(StoryFolder(user_id=test_user.id, name="Favorites"))
        db_session.commit()
        resp = client.get("/stories/folders/list", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Favorites"
        assert data[0]["story_count"] == 0

    def test_story_count_reflects_memberships(self, client, test_user, sample_story, auth_headers, db_session):
        folder = StoryFolder(user_id=test_user.id, name="Horror")
        db_session.add(folder)
        db_session.commit()
        db_session.refresh(folder)
        db_session.add(StoryFolderMembership(folder_id=folder.id, story_id=sample_story.id))
        db_session.commit()
        resp = client.get("/stories/folders/list", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()[0]["story_count"] == 1

    def test_requires_auth(self, client, db_session):
        resp = client.get("/stories/folders/list")
        assert resp.status_code == 401

    def test_folders_isolated_per_user(self, client, test_user, auth_headers, db_session):
        from app.auth import hash_password, create_access_token
        other = User(username="other", password_hash=hash_password("pass"), is_admin=False)
        db_session.add(other)
        db_session.commit()
        db_session.refresh(other)
        db_session.add(StoryFolder(user_id=other.id, name="OtherFolder"))
        db_session.commit()
        resp = client.get("/stories/folders/list", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []


class TestCreateFolder:
    def test_create_folder(self, client, auth_headers, db_session):
        resp = client.post("/stories/folders/create", json={"name": "My Folder"}, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "My Folder"
        assert data["story_count"] == 0
        assert "id" in data

    def test_create_folder_strips_whitespace(self, client, auth_headers, db_session):
        resp = client.post("/stories/folders/create", json={"name": "  Spooky  "}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Spooky"

    def test_create_folder_empty_name_rejected(self, client, auth_headers, db_session):
        resp = client.post("/stories/folders/create", json={"name": ""}, headers=auth_headers)
        assert resp.status_code == 400

    def test_create_folder_whitespace_only_name_rejected(self, client, auth_headers, db_session):
        resp = client.post("/stories/folders/create", json={"name": "   "}, headers=auth_headers)
        assert resp.status_code == 400

    def test_create_duplicate_folder_name_rejected(self, client, auth_headers, db_session):
        client.post("/stories/folders/create", json={"name": "Duplicated"}, headers=auth_headers)
        resp = client.post("/stories/folders/create", json={"name": "Duplicated"}, headers=auth_headers)
        assert resp.status_code == 409

    def test_same_name_allowed_for_different_users(self, client, auth_headers, db_session):
        from app.auth import hash_password, create_access_token
        other = User(username="other2", password_hash=hash_password("pass"), is_admin=False)
        db_session.add(other)
        db_session.commit()
        db_session.refresh(other)
        other_headers = {"Authorization": f"Bearer {create_access_token(other.id, other.username)}"}
        resp1 = client.post("/stories/folders/create", json={"name": "SharedName"}, headers=auth_headers)
        resp2 = client.post("/stories/folders/create", json={"name": "SharedName"}, headers=other_headers)
        assert resp1.status_code == 200
        assert resp2.status_code == 200

    def test_create_folder_requires_auth(self, client, db_session):
        resp = client.post("/stories/folders/create", json={"name": "No Auth"})
        assert resp.status_code == 401


class TestDeleteFolder:
    def test_delete_folder(self, client, test_user, auth_headers, db_session):
        folder = StoryFolder(user_id=test_user.id, name="ToDelete")
        db_session.add(folder)
        db_session.commit()
        db_session.refresh(folder)
        resp = client.delete(f"/stories/folders/{folder.id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert db_session.query(StoryFolder).filter(StoryFolder.id == folder.id).first() is None

    def test_delete_folder_removes_memberships(self, client, test_user, sample_story, auth_headers, db_session):
        folder = StoryFolder(user_id=test_user.id, name="WithStories")
        db_session.add(folder)
        db_session.commit()
        db_session.refresh(folder)
        db_session.add(StoryFolderMembership(folder_id=folder.id, story_id=sample_story.id))
        db_session.commit()
        client.delete(f"/stories/folders/{folder.id}", headers=auth_headers)
        assert db_session.query(StoryFolderMembership).filter(
            StoryFolderMembership.folder_id == folder.id
        ).count() == 0

    def test_delete_nonexistent_folder_returns_404(self, client, auth_headers, db_session):
        resp = client.delete("/stories/folders/9999", headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_another_users_folder_returns_404(self, client, auth_headers, db_session):
        from app.auth import hash_password
        other = User(username="other3", password_hash=hash_password("pass"), is_admin=False)
        db_session.add(other)
        db_session.commit()
        db_session.refresh(other)
        folder = StoryFolder(user_id=other.id, name="OtherFolder")
        db_session.add(folder)
        db_session.commit()
        db_session.refresh(folder)
        resp = client.delete(f"/stories/folders/{folder.id}", headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_folder_requires_auth(self, client, test_user, db_session):
        folder = StoryFolder(user_id=test_user.id, name="NeedsAuth")
        db_session.add(folder)
        db_session.commit()
        db_session.refresh(folder)
        resp = client.delete(f"/stories/folders/{folder.id}")
        assert resp.status_code == 401


class TestAddStoryToFolder:
    def test_add_story_to_folder(self, client, test_user, sample_story, auth_headers, db_session):
        folder = StoryFolder(user_id=test_user.id, name="Reads")
        db_session.add(folder)
        db_session.commit()
        db_session.refresh(folder)
        resp = client.post(f"/stories/folders/{folder.id}/add",
                           json={"story_id": sample_story.id}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert db_session.query(StoryFolderMembership).filter(
            StoryFolderMembership.folder_id == folder.id,
            StoryFolderMembership.story_id == sample_story.id,
        ).first() is not None

    def test_add_story_already_in_folder_returns_ok(self, client, test_user, sample_story, auth_headers, db_session):
        folder = StoryFolder(user_id=test_user.id, name="Reads2")
        db_session.add(folder)
        db_session.commit()
        db_session.refresh(folder)
        db_session.add(StoryFolderMembership(folder_id=folder.id, story_id=sample_story.id))
        db_session.commit()
        resp = client.post(f"/stories/folders/{folder.id}/add",
                           json={"story_id": sample_story.id}, headers=auth_headers)
        assert resp.status_code == 200
        assert "already in folder" in resp.json().get("message", "")

    def test_add_story_nonexistent_folder_returns_404(self, client, sample_story, auth_headers, db_session):
        resp = client.post("/stories/folders/9999/add",
                           json={"story_id": sample_story.id}, headers=auth_headers)
        assert resp.status_code == 404

    def test_add_nonexistent_story_returns_404(self, client, test_user, auth_headers, db_session):
        folder = StoryFolder(user_id=test_user.id, name="Reads3")
        db_session.add(folder)
        db_session.commit()
        db_session.refresh(folder)
        resp = client.post(f"/stories/folders/{folder.id}/add",
                           json={"story_id": 9999}, headers=auth_headers)
        assert resp.status_code == 404

    def test_add_story_to_another_users_folder_returns_404(self, client, sample_story, auth_headers, db_session):
        from app.auth import hash_password
        other = User(username="other4", password_hash=hash_password("pass"), is_admin=False)
        db_session.add(other)
        db_session.commit()
        db_session.refresh(other)
        folder = StoryFolder(user_id=other.id, name="OtherReads")
        db_session.add(folder)
        db_session.commit()
        db_session.refresh(folder)
        resp = client.post(f"/stories/folders/{folder.id}/add",
                           json={"story_id": sample_story.id}, headers=auth_headers)
        assert resp.status_code == 404

    def test_add_story_requires_auth(self, client, test_user, sample_story, db_session):
        folder = StoryFolder(user_id=test_user.id, name="Reads4")
        db_session.add(folder)
        db_session.commit()
        db_session.refresh(folder)
        resp = client.post(f"/stories/folders/{folder.id}/add", json={"story_id": sample_story.id})
        assert resp.status_code == 401


class TestRemoveStoryFromFolder:
    def test_remove_story_from_folder(self, client, test_user, sample_story, auth_headers, db_session):
        folder = StoryFolder(user_id=test_user.id, name="ToRemove")
        db_session.add(folder)
        db_session.commit()
        db_session.refresh(folder)
        db_session.add(StoryFolderMembership(folder_id=folder.id, story_id=sample_story.id))
        db_session.commit()
        resp = client.delete(f"/stories/folders/{folder.id}/stories/{sample_story.id}",
                             headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert db_session.query(StoryFolderMembership).filter(
            StoryFolderMembership.folder_id == folder.id,
            StoryFolderMembership.story_id == sample_story.id,
        ).first() is None

    def test_remove_story_nonexistent_folder_returns_404(self, client, sample_story, auth_headers, db_session):
        resp = client.delete(f"/stories/folders/9999/stories/{sample_story.id}",
                             headers=auth_headers)
        assert resp.status_code == 404

    def test_remove_story_from_another_users_folder_returns_404(self, client, sample_story, auth_headers, db_session):
        from app.auth import hash_password
        other = User(username="other5", password_hash=hash_password("pass"), is_admin=False)
        db_session.add(other)
        db_session.commit()
        db_session.refresh(other)
        folder = StoryFolder(user_id=other.id, name="OtherRemove")
        db_session.add(folder)
        db_session.commit()
        db_session.refresh(folder)
        resp = client.delete(f"/stories/folders/{folder.id}/stories/{sample_story.id}",
                             headers=auth_headers)
        assert resp.status_code == 404

    def test_remove_story_requires_auth(self, client, test_user, sample_story, db_session):
        folder = StoryFolder(user_id=test_user.id, name="ToRemove2")
        db_session.add(folder)
        db_session.commit()
        db_session.refresh(folder)
        resp = client.delete(f"/stories/folders/{folder.id}/stories/{sample_story.id}")
        assert resp.status_code == 401
