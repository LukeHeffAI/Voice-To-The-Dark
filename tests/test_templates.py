"""Comprehensive tests for all Jinja2 template rendering.

Verifies that every template renders correctly with expected context variables,
handles None/missing values gracefully, and returns appropriate status codes.
"""

import json

from app.models.story import Story, StoryFolder, StoryFolderMembership, StoryView
from app.auth import create_access_token


def _auth_cookie(auth_headers: dict) -> dict:
    """Extract the token from auth headers and return it as a cookie dict."""
    token = auth_headers["Authorization"].replace("Bearer ", "")
    return {"auth_token": token}


def _make_script_json() -> str:
    """Return a valid NarrationScript JSON string for testing."""
    return json.dumps({
        "title": "Test Script",
        "characters": {
            "narrator": {"voice_profile": "deep, steady, ominous", "voice_id": None},
            "character_a": {"voice_profile": "young, nervous", "voice_id": None},
        },
        "segments": [
            {"type": "narration", "character": "narrator",
             "text": "The house was dark.", "tone": "foreboding"},
            {"type": "dialogue", "character": "character_a",
             "text": "Who is there?", "tone": "frightened"},
            {"type": "sfx", "description": "door creaking slowly"},
            {"type": "ambient", "description": "wind howling", "loop": True},
            {"type": "pause", "duration_ms": 1500},
        ],
    })


# ---------------------------------------------------------------------------
# 1. Story List Page (GET /)
# ---------------------------------------------------------------------------
class TestStoryListPage:
    """Tests for the story list / home page template (story_list.html)."""

    def test_renders_with_empty_db(self, client, db_session):
        """Home page renders successfully with no stories in the database."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Voice In The Dark" in resp.text

    def test_contains_empty_state_message(self, client, db_session):
        """Empty state shows a helpful message when there are no stories."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert "No stories yet" in resp.text

    def test_contains_submit_link(self, client, db_session):
        """Home page always contains a link to submit new stories."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert "/submit" in resp.text
        assert "Submit a new story" in resp.text

    def test_renders_with_stories(self, client, sample_story, db_session):
        """Home page shows story cards when stories exist."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert sample_story.title in resp.text

    def test_contains_story_card_elements(self, client, sample_story, db_session):
        """Story cards include title and part count."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert "story-card-title" in resp.text
        assert "story-card-meta" in resp.text
        assert "1 part" in resp.text

    def test_badge_shows_fetched_for_text_only_story(self, client, sample_story, db_session):
        """A story with no script or audio shows the 'Fetched' badge."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Fetched" in resp.text

    def test_badge_shows_script_ready(self, client, db_session):
        """A story with script_json but no audio shows 'Script ready'."""
        story = Story(
            title="Script Story",
            text_content="Some text.",
            narration_text="Some text.",
            content_hash="script_hash",
            script_json=_make_script_json(),
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()

        resp = client.get("/")
        assert resp.status_code == 200
        assert "Script ready" in resp.text

    def test_badge_shows_ready_to_listen(self, client, db_session):
        """A story with audio shows 'Ready to listen'."""
        story = Story(
            title="Audio Story",
            text_content="Some text.",
            narration_text="Some text.",
            content_hash="audio_hash",
            audio_file_path="/tmp/fake_audio.mp3",
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()

        resp = client.get("/")
        assert resp.status_code == 200
        assert "Ready to listen" in resp.text

    def test_audio_story_links_to_listen_page(self, client, db_session):
        """Story with audio links to /listen/{id} instead of /story/{id}."""
        story = Story(
            title="Linked Audio Story",
            text_content="Some text.",
            narration_text="Some text.",
            content_hash="linked_audio_hash",
            audio_file_path="/tmp/fake.mp3",
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()

        resp = client.get("/")
        assert resp.status_code == 200
        assert f"/listen/{story.id}" in resp.text

    def test_text_only_story_links_to_detail_page(self, client, sample_story, db_session):
        """Story without audio links to /story/{id}."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert f"/story/{sample_story.id}" in resp.text

    def test_shows_sign_in_link_for_anonymous(self, client, db_session):
        """Anonymous users see a Sign in link."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Sign in" in resp.text

    def test_shows_username_for_authenticated_user(self, client, db_session, test_user, auth_headers):
        """Authenticated users see their username."""
        resp = client.get("/", headers=auth_headers, cookies=_auth_cookie(auth_headers))
        assert resp.status_code == 200
        assert test_user.username in resp.text

    def test_shows_recently_viewed_for_authenticated_user(self, client, db_session, test_user, auth_headers):
        """Authenticated users see the 'Recently Viewed' section label."""
        resp = client.get("/", headers=auth_headers, cookies=_auth_cookie(auth_headers))
        assert resp.status_code == 200
        assert "Recently Viewed" in resp.text

    def test_multiple_part_story_shows_plural(self, client, db_session):
        """Stories with more than one part show 'parts' (plural)."""
        story = Story(
            title="Multi-Part",
            text_content="Part 1. Part 2.",
            narration_text="Part 1. Part 2.",
            content_hash="multi_hash",
            part_count=3,
        )
        db_session.add(story)
        db_session.commit()

        resp = client.get("/")
        assert resp.status_code == 200
        assert "3 parts" in resp.text

    def test_shows_folders_for_authenticated_user_with_folders(
        self, client, db_session, test_user, auth_headers
    ):
        """Folder navigation pills appear when the user has folders."""
        folder = StoryFolder(user_id=test_user.id, name="My Favorites")
        db_session.add(folder)
        db_session.commit()

        resp = client.get("/", headers=auth_headers, cookies=_auth_cookie(auth_headers))
        assert resp.status_code == 200
        assert "My Favorites" in resp.text
        assert "folder-pill" in resp.text


# ---------------------------------------------------------------------------
# 2. Story Detail Page (GET /story/{id})
# ---------------------------------------------------------------------------
class TestStoryDetailPage:
    """Tests for the story detail page template (story_detail.html)."""

    def test_renders_with_valid_story(self, client, sample_story, db_session):
        """Detail page renders for an existing story."""
        resp = client.get(f"/story/{sample_story.id}")
        assert resp.status_code == 200
        assert sample_story.title in resp.text

    def test_shows_correct_title(self, client, sample_story, db_session):
        """The story title appears in the page body and the <title> tag."""
        resp = client.get(f"/story/{sample_story.id}")
        assert resp.status_code == 200
        assert "The Haunted House" in resp.text
        assert "<title>The Haunted House</title>" in resp.text

    def test_404_for_missing_story(self, client, db_session):
        """Returns 404 for a non-existent story ID."""
        resp = client.get("/story/99999")
        assert resp.status_code == 404

    def test_handles_none_narration_text(self, client, db_session):
        """Template does not crash when narration_text is None."""
        story = Story(
            title="Null Narration",
            text_content="Some raw text.",
            narration_text=None,
            content_hash="null_narration_hash",
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(f"/story/{story.id}")
        assert resp.status_code == 200
        assert "0 characters" in resp.text

    def test_handles_none_audio_file_path(self, client, sample_story, db_session):
        """Template renders correctly when audio_file_path is None (no listen button)."""
        resp = client.get(f"/story/{sample_story.id}")
        assert resp.status_code == 200
        # Should not show the listen button since there's no audio
        assert "Listen Now" not in resp.text

    def test_shows_listen_button_when_audio_exists(self, client, db_session):
        """Template shows 'Listen Now' button when audio_file_path is set."""
        story = Story(
            title="Audio Ready Story",
            text_content="Text content here.",
            narration_text="Narration text.",
            content_hash="audio_ready_hash",
            audio_file_path="/tmp/test_audio.mp3",
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(f"/story/{story.id}")
        assert resp.status_code == 200
        assert "Listen Now" in resp.text
        assert f"/listen/{story.id}" in resp.text

    def test_shows_script_stats_when_script_present(self, client, db_session):
        """Template displays segment/voice/sfx counts when script_json exists."""
        story = Story(
            title="Script Stats Story",
            text_content="Story text.",
            narration_text="Narration text.",
            content_hash="script_stats_hash",
            script_json=_make_script_json(),
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(f"/story/{story.id}")
        assert resp.status_code == 200
        assert "5 segments" in resp.text
        assert "2 voice" in resp.text
        assert "1 SFX" in resp.text

    def test_shows_edit_script_link_when_script_exists(self, client, db_session):
        """Template includes an 'Edit Script' link when the story has a script."""
        story = Story(
            title="Editable Script Story",
            text_content="Text.",
            narration_text="Narration.",
            content_hash="edit_script_hash",
            script_json=_make_script_json(),
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(f"/story/{story.id}")
        assert resp.status_code == 200
        assert "Edit Script" in resp.text
        assert f"/story/{story.id}/edit-script" in resp.text

    def test_shows_generate_script_button_when_no_script(
        self, client, db_session, test_user, auth_headers
    ):
        """Authenticated users see 'Generate Script' when no script exists."""
        story = Story(
            title="No Script Story",
            text_content="Text.",
            narration_text="Narration.",
            content_hash="no_script_hash",
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(
            f"/story/{story.id}",
            headers=auth_headers,
            cookies=_auth_cookie(auth_headers),
        )
        assert resp.status_code == 200
        assert "Generate Script" in resp.text

    def test_shows_login_prompt_when_anonymous(self, client, sample_story, db_session):
        """Anonymous users see a login prompt instead of generate buttons."""
        resp = client.get(f"/story/{sample_story.id}")
        assert resp.status_code == 200
        assert "Sign in" in resp.text

    def test_shows_teaser_text(self, client, sample_story, db_session):
        """Detail page includes a teaser excerpt from the narration text."""
        resp = client.get(f"/story/{sample_story.id}")
        assert resp.status_code == 200
        assert "story-teaser" in resp.text

    def test_shows_word_count(self, client, sample_story, db_session):
        """Detail page shows the word count."""
        resp = client.get(f"/story/{sample_story.id}")
        assert resp.status_code == 200
        assert "words" in resp.text

    def test_shows_read_story_link(self, client, sample_story, db_session):
        """Detail page includes a 'Read Story' link."""
        resp = client.get(f"/story/{sample_story.id}")
        assert resp.status_code == 200
        assert "Read Story" in resp.text
        assert f"/read/{sample_story.id}" in resp.text

    def test_shows_back_link(self, client, sample_story, db_session):
        """Detail page includes a back link to the home page."""
        resp = client.get(f"/story/{sample_story.id}")
        assert resp.status_code == 200
        assert "All stories" in resp.text

    def test_shows_author_when_present(self, client, db_session):
        """Detail page shows author name when set."""
        story = Story(
            title="Authored Story",
            text_content="Text.",
            narration_text="Narration.",
            content_hash="authored_hash",
            author="spooky_writer",
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(f"/story/{story.id}")
        assert resp.status_code == 200
        assert "spooky_writer" in resp.text

    def test_shows_reddit_link_when_url_present(self, client, sample_story, db_session):
        """Detail page includes 'View on Reddit' link when reddit_url is set."""
        resp = client.get(f"/story/{sample_story.id}")
        assert resp.status_code == 200
        assert "View on Reddit" in resp.text

    def test_pipeline_steps_present(self, client, sample_story, db_session):
        """Detail page includes the three pipeline steps."""
        resp = client.get(f"/story/{sample_story.id}")
        assert resp.status_code == 200
        assert "Story Fetched" in resp.text
        assert "Narration Script" in resp.text
        assert "Audio Narration" in resp.text


# ---------------------------------------------------------------------------
# 3. Submit Page (GET /submit)
# ---------------------------------------------------------------------------
class TestSubmitPage:
    """Tests for the submit page template (submit.html)."""

    def test_renders_successfully(self, client, db_session):
        """Submit page renders with a 200 status."""
        resp = client.get("/submit")
        assert resp.status_code == 200

    def test_contains_page_title(self, client, db_session):
        """Submit page shows the 'Submit a Story' heading."""
        resp = client.get("/submit")
        assert resp.status_code == 200
        assert "Submit a Story" in resp.text

    def test_contains_browse_section(self, client, db_session):
        """Submit page includes the 'Best of r/nosleep' browsing section."""
        resp = client.get("/submit")
        assert resp.status_code == 200
        assert "Best of r/nosleep" in resp.text

    def test_contains_filter_buttons(self, client, db_session):
        """Submit page has time filter buttons."""
        resp = client.get("/submit")
        assert resp.status_code == 200
        assert "All Time" in resp.text
        assert "This Year" in resp.text
        assert "This Month" in resp.text
        assert "This Week" in resp.text

    def test_contains_back_link(self, client, db_session):
        """Submit page has a back link to the home page."""
        resp = client.get("/submit")
        assert resp.status_code == 200
        assert "All stories" in resp.text

    def test_shows_login_prompt_for_anonymous(self, client, db_session):
        """Anonymous users see a login prompt on the submit page."""
        resp = client.get("/submit")
        assert resp.status_code == 200
        assert "Sign in to submit stories" in resp.text

    def test_shows_manual_entry_for_authenticated(self, client, db_session, test_user, auth_headers):
        """Authenticated users see the Manual Entry button."""
        resp = client.get("/submit", headers=auth_headers, cookies=_auth_cookie(auth_headers))
        assert resp.status_code == 200
        assert "Manual Entry" in resp.text

    def test_contains_manual_form_elements(self, client, db_session):
        """Submit page includes the manual entry form fields in the popout."""
        resp = client.get("/submit")
        assert resp.status_code == 200
        assert "manualUrl" in resp.text
        assert "manualTitle" in resp.text
        assert "manualText" in resp.text

    def test_no_login_prompt_for_authenticated(self, client, db_session, test_user, auth_headers):
        """Authenticated users do not see the login prompt on submit."""
        resp = client.get("/submit", headers=auth_headers, cookies=_auth_cookie(auth_headers))
        assert resp.status_code == 200
        assert "Sign in to submit stories" not in resp.text


# ---------------------------------------------------------------------------
# 4. Login Page (GET /login)
# ---------------------------------------------------------------------------
class TestLoginPage:
    """Tests for the login page template (login.html)."""

    def test_renders_login_form(self, client, db_session):
        """Login page renders with form elements."""
        resp = client.get("/login")
        assert resp.status_code == 200

    def test_contains_title(self, client, db_session):
        """Login page shows 'Voice In The Dark'."""
        resp = client.get("/login")
        assert "Voice In The Dark" in resp.text

    def test_contains_sign_in_subtitle(self, client, db_session):
        """Login page includes 'Sign in to continue'."""
        resp = client.get("/login")
        assert "Sign in to continue" in resp.text

    def test_contains_username_field(self, client, db_session):
        """Login page has a username input field."""
        resp = client.get("/login")
        assert 'id="username"' in resp.text
        assert "Username" in resp.text

    def test_contains_password_field(self, client, db_session):
        """Login page has a password input field."""
        resp = client.get("/login")
        assert 'id="password"' in resp.text
        assert "Password" in resp.text

    def test_contains_submit_button(self, client, db_session):
        """Login page has a Sign In button."""
        resp = client.get("/login")
        assert "Sign In" in resp.text
        assert "loginBtn" in resp.text

    def test_contains_back_link(self, client, db_session):
        """Login page has a back link to stories."""
        resp = client.get("/login")
        assert "Back to stories" in resp.text

    def test_page_title(self, client, db_session):
        """Login page <title> tag contains 'Sign In'."""
        resp = client.get("/login")
        assert "Sign In" in resp.text


# ---------------------------------------------------------------------------
# 5. Player Page (GET /listen/{id})
# ---------------------------------------------------------------------------
class TestPlayerPage:
    """Tests for the audio player page template (player.html)."""

    def test_404_for_missing_story(self, client, db_session):
        """Returns 404 when story ID does not exist."""
        resp = client.get("/listen/99999")
        assert resp.status_code == 404

    def test_404_for_story_without_audio(self, client, sample_story, db_session):
        """Returns 404 when the story has no audio_file_path."""
        resp = client.get(f"/listen/{sample_story.id}")
        assert resp.status_code == 404

    def test_renders_with_audio_story(self, client, db_session):
        """Player page renders for a story that has audio."""
        story = Story(
            title="Listenable Story",
            text_content="Story text.",
            narration_text="Narration text.",
            content_hash="listenable_hash",
            audio_file_path="/tmp/test_listen.mp3",
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(f"/listen/{story.id}")
        assert resp.status_code == 200
        assert "Listenable Story" in resp.text

    def test_contains_player_controls(self, client, db_session):
        """Player page includes play button and progress bar."""
        story = Story(
            title="Player Controls Story",
            text_content="Text.",
            narration_text="Narration.",
            content_hash="controls_hash",
            audio_file_path="/tmp/test_controls.mp3",
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(f"/listen/{story.id}")
        assert resp.status_code == 200
        assert "playBtn" in resp.text
        assert "progressBar" in resp.text
        assert "speedSlider" in resp.text

    def test_contains_skip_buttons(self, client, db_session):
        """Player page has skip forward/back and prev/next buttons."""
        story = Story(
            title="Skip Buttons Story",
            text_content="Text.",
            narration_text="Narration.",
            content_hash="skip_hash",
            audio_file_path="/tmp/test_skip.mp3",
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(f"/listen/{story.id}")
        assert resp.status_code == 200
        assert "skipBackBtn" in resp.text
        assert "skipFwdBtn" in resp.text
        assert "prevBtn" in resp.text
        assert "nextBtn" in resp.text

    def test_contains_download_link(self, client, db_session):
        """Player page includes a Download MP3 link."""
        story = Story(
            title="Download Story",
            text_content="Text.",
            narration_text="Narration.",
            content_hash="download_hash",
            audio_file_path="/tmp/test_download.mp3",
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(f"/listen/{story.id}")
        assert resp.status_code == 200
        assert "Download MP3" in resp.text
        assert f"/download/{story.id}" in resp.text

    def test_contains_story_detail_link(self, client, db_session):
        """Player page links back to the story detail / script page."""
        story = Story(
            title="Detail Link Story",
            text_content="Text.",
            narration_text="Narration.",
            content_hash="detail_link_hash",
            audio_file_path="/tmp/test_detail_link.mp3",
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(f"/listen/{story.id}")
        assert resp.status_code == 200
        assert f"/story/{story.id}" in resp.text
        assert "Script" in resp.text

    def test_shows_author_when_present(self, client, db_session):
        """Player page displays the author if available."""
        story = Story(
            title="Author Player Story",
            text_content="Text.",
            narration_text="Narration.",
            content_hash="author_player_hash",
            audio_file_path="/tmp/test_author.mp3",
            author="creepy_author",
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(f"/listen/{story.id}")
        assert resp.status_code == 200
        assert "creepy_author" in resp.text

    def test_contains_speed_control(self, client, db_session):
        """Player page includes the playback speed control."""
        story = Story(
            title="Speed Control Story",
            text_content="Text.",
            narration_text="Narration.",
            content_hash="speed_hash",
            audio_file_path="/tmp/test_speed.mp3",
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(f"/listen/{story.id}")
        assert resp.status_code == 200
        assert "Speed" in resp.text
        assert "speedInput" in resp.text

    def test_contains_eq_visualizer(self, client, db_session):
        """Player page includes the EQ visualizer artwork."""
        story = Story(
            title="EQ Viz Story",
            text_content="Text.",
            narration_text="Narration.",
            content_hash="eq_hash",
            audio_file_path="/tmp/test_eq.mp3",
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(f"/listen/{story.id}")
        assert resp.status_code == 200
        assert "eq-viz" in resp.text
        assert "eq-bar" in resp.text


# ---------------------------------------------------------------------------
# 6. Reader Page (GET /read/{id})
# ---------------------------------------------------------------------------
class TestReaderPage:
    """Tests for the reader page template (reader.html)."""

    def test_renders_with_valid_story(self, client, sample_story, db_session):
        """Reader page renders for an existing story with text_content."""
        resp = client.get(f"/read/{sample_story.id}")
        assert resp.status_code == 200
        assert sample_story.title in resp.text

    def test_404_for_missing_story(self, client, db_session):
        """Returns 404 when story ID does not exist."""
        resp = client.get("/read/99999")
        assert resp.status_code == 404

    def test_404_for_story_without_text(self, client, db_session):
        """Returns 404 when the story has no text_content."""
        story = Story(
            title="No Text Story",
            text_content="",
            narration_text="",
            content_hash="no_text_hash",
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(f"/read/{story.id}")
        assert resp.status_code == 404

    def test_shows_story_title(self, client, sample_story, db_session):
        """Reader page displays the story title in the header."""
        resp = client.get(f"/read/{sample_story.id}")
        assert resp.status_code == 200
        assert "reader-title" in resp.text
        assert sample_story.title in resp.text

    def test_shows_word_count(self, client, sample_story, db_session):
        """Reader page displays word count."""
        resp = client.get(f"/read/{sample_story.id}")
        assert resp.status_code == 200
        assert "words" in resp.text

    def test_shows_read_time(self, client, db_session):
        """Reader page shows estimated reading time for longer text."""
        # Create a story with enough words to get a non-zero read time (~230+ words)
        long_text = " ".join(["word"] * 500)
        story = Story(
            title="Long Read Story",
            text_content=long_text,
            narration_text=long_text,
            content_hash="long_read_hash",
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(f"/read/{story.id}")
        assert resp.status_code == 200
        assert "min read" in resp.text

    def test_handles_long_text(self, client, db_session):
        """Reader page handles very long story text without crashing."""
        long_text = "This is a sentence. " * 5000
        story = Story(
            title="Very Long Story",
            text_content=long_text,
            narration_text=long_text,
            content_hash="very_long_hash",
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(f"/read/{story.id}")
        assert resp.status_code == 200
        assert "Very Long Story" in resp.text

    def test_renders_paragraphs(self, client, db_session):
        """Reader page splits text into paragraphs."""
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        story = Story(
            title="Paragraph Story",
            text_content=text,
            narration_text=text,
            content_hash="paragraph_hash",
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(f"/read/{story.id}")
        assert resp.status_code == 200
        assert "First paragraph." in resp.text
        assert "Second paragraph." in resp.text
        assert "Third paragraph." in resp.text

    def test_renders_section_breaks(self, client, db_session):
        """Reader page renders horizontal rule separators."""
        text = "Before the break.\n\n---\n\nAfter the break."
        story = Story(
            title="Section Break Story",
            text_content=text,
            narration_text=text,
            content_hash="section_break_hash",
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(f"/read/{story.id}")
        assert resp.status_code == 200
        assert "<hr" in resp.text

    def test_contains_story_detail_link(self, client, sample_story, db_session):
        """Reader page links back to the story detail page."""
        resp = client.get(f"/read/{sample_story.id}")
        assert resp.status_code == 200
        assert f"/story/{sample_story.id}" in resp.text
        assert "Story Details" in resp.text

    def test_shows_listen_link_when_audio_exists(self, client, db_session):
        """Reader page shows a Listen link when story has audio."""
        story = Story(
            title="Reader Audio Story",
            text_content="Some text content here.",
            narration_text="Some narration text.",
            content_hash="reader_audio_hash",
            audio_file_path="/tmp/reader_audio.mp3",
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(f"/read/{story.id}")
        assert resp.status_code == 200
        assert "Listen" in resp.text
        assert f"/listen/{story.id}" in resp.text

    def test_no_listen_link_when_no_audio(self, client, sample_story, db_session):
        """Reader page does not show a Listen link when there is no audio."""
        resp = client.get(f"/read/{sample_story.id}")
        assert resp.status_code == 200
        # The Listen link only appears in the footer; verify it's not present
        # (but "Listen" might appear in other contexts, so check the href form)
        assert f"/listen/{sample_story.id}" not in resp.text

    def test_shows_reading_progress_bar(self, client, sample_story, db_session):
        """Reader page includes the reading progress bar element."""
        resp = client.get(f"/read/{sample_story.id}")
        assert resp.status_code == 200
        assert "readingProgress" in resp.text

    def test_shows_author_when_present(self, client, db_session):
        """Reader page displays the author."""
        story = Story(
            title="Reader Author Story",
            text_content="Content here.",
            narration_text="Narration here.",
            content_hash="reader_author_hash",
            author="nighttime_writer",
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(f"/read/{story.id}")
        assert resp.status_code == 200
        assert "nighttime_writer" in resp.text


# ---------------------------------------------------------------------------
# 7. Script Editor (GET /story/{id}/edit-script)
# ---------------------------------------------------------------------------
class TestScriptEditorPage:
    """Tests for the script editor page template (script_editor.html)."""

    def test_renders_for_story_with_script(self, client, db_session):
        """Script editor renders when the story has script_json."""
        story = Story(
            title="Script Editor Story",
            text_content="Text.",
            narration_text="Narration.",
            content_hash="script_editor_hash",
            script_json=_make_script_json(),
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(f"/story/{story.id}/edit-script")
        assert resp.status_code == 200
        assert "Edit Script" in resp.text
        assert "Script Editor Story" in resp.text

    def test_404_for_missing_story(self, client, db_session):
        """Returns 404 for non-existent story ID."""
        resp = client.get("/story/99999/edit-script")
        assert resp.status_code == 404

    def test_404_for_story_without_script(self, client, sample_story, db_session):
        """Returns 404 when the story has no script_json."""
        resp = client.get(f"/story/{sample_story.id}/edit-script")
        assert resp.status_code == 404

    def test_contains_character_panel(self, client, db_session):
        """Script editor contains the Characters & Voices panel."""
        story = Story(
            title="Char Panel Story",
            text_content="Text.",
            narration_text="Narration.",
            content_hash="char_panel_hash",
            script_json=_make_script_json(),
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(f"/story/{story.id}/edit-script")
        assert resp.status_code == 200
        assert "Characters" in resp.text
        assert "Voices" in resp.text
        assert "characterList" in resp.text

    def test_contains_segments_section(self, client, db_session):
        """Script editor contains the Segments section."""
        story = Story(
            title="Segments Story",
            text_content="Text.",
            narration_text="Narration.",
            content_hash="segments_hash",
            script_json=_make_script_json(),
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(f"/story/{story.id}/edit-script")
        assert resp.status_code == 200
        assert "Segments" in resp.text
        assert "segmentList" in resp.text

    def test_contains_save_button(self, client, db_session):
        """Script editor includes a Save Changes button."""
        story = Story(
            title="Save Button Story",
            text_content="Text.",
            narration_text="Narration.",
            content_hash="save_btn_hash",
            script_json=_make_script_json(),
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(f"/story/{story.id}/edit-script")
        assert resp.status_code == 200
        assert "Save Changes" in resp.text
        assert "saveBtn" in resp.text

    def test_contains_back_link(self, client, db_session):
        """Script editor has a back link to the story detail page."""
        story = Story(
            title="Back Link Story",
            text_content="Text.",
            narration_text="Narration.",
            content_hash="back_link_hash",
            script_json=_make_script_json(),
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(f"/story/{story.id}/edit-script")
        assert resp.status_code == 200
        assert "Back to story" in resp.text
        assert f"/story/{story.id}" in resp.text

    def test_script_json_embedded_in_page(self, client, db_session):
        """Script editor embeds the script JSON in the page for JavaScript."""
        story = Story(
            title="Embedded JSON Story",
            text_content="Text.",
            narration_text="Narration.",
            content_hash="embedded_json_hash",
            script_json=_make_script_json(),
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(f"/story/{story.id}/edit-script")
        assert resp.status_code == 200
        # The script JSON and voice pool JSON should be embedded
        assert "voice_pool_json" not in resp.text or "voicePool" in resp.text
        assert "let script =" in resp.text

    def test_contains_voice_pool_json(self, client, db_session):
        """Script editor embeds the voice pool data for voice selection dropdowns."""
        story = Story(
            title="Voice Pool Story",
            text_content="Text.",
            narration_text="Narration.",
            content_hash="voice_pool_hash",
            script_json=_make_script_json(),
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(f"/story/{story.id}/edit-script")
        assert resp.status_code == 200
        assert "voicePool" in resp.text


# ---------------------------------------------------------------------------
# 8. Settings Page (GET /settings/)
# ---------------------------------------------------------------------------
class TestSettingsPage:
    """Tests for the settings page template (settings.html)."""

    def test_unauthenticated_shows_login(self, client, db_session):
        """Unauthenticated access renders the login page instead of settings."""
        resp = client.get("/settings/")
        assert resp.status_code == 200
        assert "Sign in" in resp.text
        # Should render login.html, not settings.html
        assert "Reddit Refresh Interval" not in resp.text

    def test_authenticated_shows_settings(self, client, db_session, test_user, auth_headers):
        """Authenticated users see the settings page."""
        resp = client.get("/settings/", headers=auth_headers, cookies=_auth_cookie(auth_headers))
        assert resp.status_code == 200
        assert "Settings" in resp.text

    def test_contains_ttl_options(self, client, db_session, test_user, auth_headers):
        """Settings page includes the Reddit TTL refresh dropdown."""
        resp = client.get("/settings/", headers=auth_headers, cookies=_auth_cookie(auth_headers))
        assert resp.status_code == 200
        assert "Reddit Refresh Interval" in resp.text
        assert "ttlSelect" in resp.text

    def test_contains_cache_status(self, client, db_session, test_user, auth_headers):
        """Settings page includes the Cache Status section."""
        resp = client.get("/settings/", headers=auth_headers, cookies=_auth_cookie(auth_headers))
        assert resp.status_code == 200
        assert "Cache Status" in resp.text

    def test_contains_upload_section(self, client, db_session, test_user, auth_headers):
        """Settings page includes the manual upload section."""
        resp = client.get("/settings/", headers=auth_headers, cookies=_auth_cookie(auth_headers))
        assert resp.status_code == 200
        assert "Manual Reddit Data Upload" in resp.text
        assert "jsonFileInput" in resp.text

    def test_contains_save_button(self, client, db_session, test_user, auth_headers):
        """Settings page has a Save button for TTL."""
        resp = client.get("/settings/", headers=auth_headers, cookies=_auth_cookie(auth_headers))
        assert resp.status_code == 200
        assert "saveTtlBtn" in resp.text

    def test_shows_username(self, client, db_session, test_user, auth_headers):
        """Settings page displays the logged-in username."""
        resp = client.get("/settings/", headers=auth_headers, cookies=_auth_cookie(auth_headers))
        assert resp.status_code == 200
        assert test_user.username in resp.text

    def test_contains_sign_out_link(self, client, db_session, test_user, auth_headers):
        """Settings page has a sign-out link."""
        resp = client.get("/settings/", headers=auth_headers, cookies=_auth_cookie(auth_headers))
        assert resp.status_code == 200
        assert "Sign out" in resp.text

    def test_contains_back_link(self, client, db_session, test_user, auth_headers):
        """Settings page has a back link to the home page."""
        resp = client.get("/settings/", headers=auth_headers, cookies=_auth_cookie(auth_headers))
        assert resp.status_code == 200
        assert "All stories" in resp.text

    def test_contains_timeframe_options_in_cache(self, client, db_session, test_user, auth_headers):
        """Settings page shows cache status for each timeframe."""
        resp = client.get("/settings/", headers=auth_headers, cookies=_auth_cookie(auth_headers))
        assert resp.status_code == 200
        # Check for capitalized timeframe names in the cache status
        assert "Alltime" in resp.text
        assert "Year" in resp.text
        assert "Month" in resp.text
        assert "Week" in resp.text
        assert "Today" in resp.text


# ---------------------------------------------------------------------------
# 9. Folder Page (GET /folder/{id})
# ---------------------------------------------------------------------------
class TestFolderPage:
    """Tests for the folder page template (folder.html)."""

    def test_401_for_unauthenticated(self, client, db_session):
        """Folder page requires authentication."""
        resp = client.get("/folder/1")
        assert resp.status_code == 401

    def test_404_for_nonexistent_folder(self, client, db_session, test_user, auth_headers):
        """Returns 404 for a folder that does not exist."""
        resp = client.get(
            "/folder/99999",
            headers=auth_headers,
            cookies=_auth_cookie(auth_headers),
        )
        assert resp.status_code == 404

    def test_404_for_other_users_folder(self, client, db_session, test_user, auth_headers, admin_user):
        """Returns 404 when accessing another user's folder."""
        folder = StoryFolder(user_id=admin_user.id, name="Admin Folder")
        db_session.add(folder)
        db_session.commit()
        db_session.refresh(folder)

        resp = client.get(
            f"/folder/{folder.id}",
            headers=auth_headers,
            cookies=_auth_cookie(auth_headers),
        )
        assert resp.status_code == 404

    def test_renders_empty_folder(self, client, db_session, test_user, auth_headers):
        """Folder page renders for an empty folder."""
        folder = StoryFolder(user_id=test_user.id, name="Empty Folder")
        db_session.add(folder)
        db_session.commit()
        db_session.refresh(folder)

        resp = client.get(
            f"/folder/{folder.id}",
            headers=auth_headers,
            cookies=_auth_cookie(auth_headers),
        )
        assert resp.status_code == 200
        assert "Empty Folder" in resp.text
        assert "This folder is empty" in resp.text

    def test_renders_folder_with_stories(self, client, db_session, test_user, auth_headers):
        """Folder page shows stories that belong to the folder."""
        story = Story(
            title="Folder Story",
            text_content="Content.",
            narration_text="Narration.",
            content_hash="folder_story_hash",
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        folder = StoryFolder(user_id=test_user.id, name="My Folder")
        db_session.add(folder)
        db_session.commit()
        db_session.refresh(folder)

        membership = StoryFolderMembership(folder_id=folder.id, story_id=story.id)
        db_session.add(membership)
        db_session.commit()

        resp = client.get(
            f"/folder/{folder.id}",
            headers=auth_headers,
            cookies=_auth_cookie(auth_headers),
        )
        assert resp.status_code == 200
        assert "Folder Story" in resp.text
        assert "My Folder" in resp.text

    def test_shows_folder_title(self, client, db_session, test_user, auth_headers):
        """Folder page shows the folder name as a title."""
        folder = StoryFolder(user_id=test_user.id, name="Horror Collection")
        db_session.add(folder)
        db_session.commit()
        db_session.refresh(folder)

        resp = client.get(
            f"/folder/{folder.id}",
            headers=auth_headers,
            cookies=_auth_cookie(auth_headers),
        )
        assert resp.status_code == 200
        assert "Horror Collection" in resp.text
        assert "folder-title" in resp.text

    def test_contains_delete_folder_button(self, client, db_session, test_user, auth_headers):
        """Folder page has a delete folder button."""
        folder = StoryFolder(user_id=test_user.id, name="Deletable Folder")
        db_session.add(folder)
        db_session.commit()
        db_session.refresh(folder)

        resp = client.get(
            f"/folder/{folder.id}",
            headers=auth_headers,
            cookies=_auth_cookie(auth_headers),
        )
        assert resp.status_code == 200
        assert "Delete folder" in resp.text

    def test_contains_folder_navigation(self, client, db_session, test_user, auth_headers):
        """Folder page shows navigation pills for all user folders."""
        folder1 = StoryFolder(user_id=test_user.id, name="Folder A")
        folder2 = StoryFolder(user_id=test_user.id, name="Folder B")
        db_session.add_all([folder1, folder2])
        db_session.commit()
        db_session.refresh(folder1)

        resp = client.get(
            f"/folder/{folder1.id}",
            headers=auth_headers,
            cookies=_auth_cookie(auth_headers),
        )
        assert resp.status_code == 200
        assert "Folder A" in resp.text
        assert "Folder B" in resp.text
        assert "Recent" in resp.text  # The home/recent pill

    def test_active_folder_highlighted(self, client, db_session, test_user, auth_headers):
        """The current folder pill has the 'active' class."""
        folder = StoryFolder(user_id=test_user.id, name="Active Folder")
        db_session.add(folder)
        db_session.commit()
        db_session.refresh(folder)

        resp = client.get(
            f"/folder/{folder.id}",
            headers=auth_headers,
            cookies=_auth_cookie(auth_headers),
        )
        assert resp.status_code == 200
        # The active folder pill should render with the 'active' class on its pill element
        assert 'class="folder-pill active"' in resp.text

    def test_contains_home_link(self, client, db_session, test_user, auth_headers):
        """Folder page has a link back to the home page."""
        folder = StoryFolder(user_id=test_user.id, name="Home Link Folder")
        db_session.add(folder)
        db_session.commit()
        db_session.refresh(folder)

        resp = client.get(
            f"/folder/{folder.id}",
            headers=auth_headers,
            cookies=_auth_cookie(auth_headers),
        )
        assert resp.status_code == 200
        assert "Home" in resp.text

    def test_shows_remove_from_folder_option(self, client, db_session, test_user, auth_headers):
        """Folder page shows a 'Remove from folder' option in story dropdown."""
        story = Story(
            title="Removable Story",
            text_content="Content.",
            narration_text="Narration.",
            content_hash="removable_hash",
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        folder = StoryFolder(user_id=test_user.id, name="Remove Folder")
        db_session.add(folder)
        db_session.commit()
        db_session.refresh(folder)

        membership = StoryFolderMembership(folder_id=folder.id, story_id=story.id)
        db_session.add(membership)
        db_session.commit()

        resp = client.get(
            f"/folder/{folder.id}",
            headers=auth_headers,
            cookies=_auth_cookie(auth_headers),
        )
        assert resp.status_code == 200
        assert "Remove from folder" in resp.text

    def test_shows_username(self, client, db_session, test_user, auth_headers):
        """Folder page displays the logged-in username."""
        folder = StoryFolder(user_id=test_user.id, name="User Folder")
        db_session.add(folder)
        db_session.commit()
        db_session.refresh(folder)

        resp = client.get(
            f"/folder/{folder.id}",
            headers=auth_headers,
            cookies=_auth_cookie(auth_headers),
        )
        assert resp.status_code == 200
        assert test_user.username in resp.text

    def test_story_badges_in_folder(self, client, db_session, test_user, auth_headers):
        """Stories in folders show appropriate status badges."""
        story_audio = Story(
            title="Audio In Folder",
            text_content="Content.",
            narration_text="Narration.",
            content_hash="audio_folder_hash",
            audio_file_path="/tmp/folder_audio.mp3",
            part_count=1,
        )
        story_text = Story(
            title="Text In Folder",
            text_content="Content.",
            narration_text="Narration.",
            content_hash="text_folder_hash",
            part_count=1,
        )
        db_session.add_all([story_audio, story_text])
        db_session.commit()
        db_session.refresh(story_audio)
        db_session.refresh(story_text)

        folder = StoryFolder(user_id=test_user.id, name="Badge Folder")
        db_session.add(folder)
        db_session.commit()
        db_session.refresh(folder)

        m1 = StoryFolderMembership(folder_id=folder.id, story_id=story_audio.id)
        m2 = StoryFolderMembership(folder_id=folder.id, story_id=story_text.id)
        db_session.add_all([m1, m2])
        db_session.commit()

        resp = client.get(
            f"/folder/{folder.id}",
            headers=auth_headers,
            cookies=_auth_cookie(auth_headers),
        )
        assert resp.status_code == 200
        assert "Ready to listen" in resp.text
        assert "Fetched" in resp.text


# ---------------------------------------------------------------------------
# 10. Base Template
# ---------------------------------------------------------------------------
class TestBaseTemplate:
    """Tests for elements that come from base.html across all pages."""

    def test_contains_html_doctype(self, client, db_session):
        """All pages include the HTML5 doctype."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert "<!DOCTYPE html>" in resp.text

    def test_contains_meta_viewport(self, client, db_session):
        """All pages include a viewport meta tag."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert "viewport" in resp.text

    def test_contains_theme_color(self, client, db_session):
        """All pages include a theme-color meta tag."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert "theme-color" in resp.text

    def test_contains_font_links(self, client, db_session):
        """All pages include Google Fonts links."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert "fonts.googleapis.com" in resp.text

    def test_contains_mini_player(self, client, db_session):
        """All pages include the persistent mini-player bar."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert "mini-player" in resp.text

    def test_contains_playlist_drawer(self, client, db_session):
        """All pages include the playlist drawer."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert "playlist-drawer" in resp.text

    def test_contains_toast_element(self, client, db_session):
        """All pages include the toast notification element."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert 'id="toast"' in resp.text

    def test_contains_fog_effect(self, client, db_session):
        """All pages include the fog atmospheric effect."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert "global-fog" in resp.text

    def test_contains_persistent_audio_element(self, client, db_session):
        """All pages include the persistent audio element."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert "persistent-audio" in resp.text


# ---------------------------------------------------------------------------
# 11. Edge Cases and Robustness
# ---------------------------------------------------------------------------
class TestTemplateEdgeCases:
    """Tests for edge cases to ensure templates don't crash."""

    def test_story_with_none_author(self, client, db_session):
        """Detail page handles story with None author gracefully."""
        story = Story(
            title="No Author Story",
            text_content="Some text.",
            narration_text="Narration.",
            content_hash="no_author_hash",
            author=None,
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(f"/story/{story.id}")
        assert resp.status_code == 200
        assert "No Author Story" in resp.text

    def test_story_with_none_reddit_url(self, client, db_session):
        """Detail page handles story with None reddit_url gracefully."""
        story = Story(
            title="No URL Story",
            text_content="Some text.",
            narration_text="Narration.",
            content_hash="no_url_hash",
            reddit_url=None,
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(f"/story/{story.id}")
        assert resp.status_code == 200
        assert "No URL Story" in resp.text
        # Should not show "View on Reddit" since there's no URL
        assert "View on Reddit" not in resp.text

    def test_story_with_empty_text_content(self, client, db_session):
        """Detail page handles empty text_content without crashing."""
        story = Story(
            title="Empty Text Story",
            text_content="",
            narration_text=None,
            content_hash="empty_text_hash",
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(f"/story/{story.id}")
        assert resp.status_code == 200

    def test_story_with_special_characters_in_title(self, client, db_session):
        """Templates handle special characters in the title correctly."""
        story = Story(
            title='<script>alert("XSS")</script> & "quotes"',
            text_content="Content with <b>HTML</b>.",
            narration_text="Narration.",
            content_hash="special_chars_hash",
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(f"/story/{story.id}")
        assert resp.status_code == 200
        # Jinja2 auto-escapes, so raw <script> should not appear
        assert "<script>alert" not in resp.text

    def test_story_detail_with_all_fields_populated(self, client, db_session):
        """Detail page renders correctly when all story fields are populated."""
        story = Story(
            title="Fully Populated Story",
            reddit_url="https://www.reddit.com/r/nosleep/comments/full/test/",
            text_content="Full content here. With multiple sentences. And more.",
            narration_text="Narration version. With sentences. Ready for reading.",
            content_hash="full_hash",
            author="prolific_writer",
            audio_file_path="/tmp/full_audio.mp3",
            script_json=_make_script_json(),
            part_count=3,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(f"/story/{story.id}")
        assert resp.status_code == 200
        assert "Fully Populated Story" in resp.text
        assert "prolific_writer" in resp.text
        assert "Listen Now" in resp.text
        assert "Edit Script" in resp.text
        assert "View on Reddit" in resp.text
        assert "3 parts" in resp.text

    def test_story_list_with_many_stories(self, client, db_session):
        """Home page handles rendering many stories."""
        for i in range(25):
            story = Story(
                title=f"Story Number {i}",
                text_content=f"Content {i}.",
                narration_text=f"Narration {i}.",
                content_hash=f"many_hash_{i}",
                part_count=1,
            )
            db_session.add(story)
        db_session.commit()

        resp = client.get("/")
        assert resp.status_code == 200
        assert "Story Number 0" in resp.text
        assert "Story Number 24" in resp.text

    def test_story_with_very_long_title(self, client, db_session):
        """Templates handle very long story titles without crashing."""
        long_title = "A" * 500
        story = Story(
            title=long_title,
            text_content="Content.",
            narration_text="Narration.",
            content_hash="long_title_hash",
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(f"/story/{story.id}")
        assert resp.status_code == 200
        assert long_title in resp.text

    def test_invalid_script_json_does_not_crash_detail(self, client, db_session):
        """Detail page handles malformed script_json without crashing."""
        story = Story(
            title="Bad Script Story",
            text_content="Content.",
            narration_text="Narration.",
            content_hash="bad_script_hash",
            script_json='{"invalid": "not a valid script"}',
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(f"/story/{story.id}")
        assert resp.status_code == 200
        assert "Bad Script Story" in resp.text
