"""Tests for the v1 → v2 data migration script."""

import json
import os
import sqlite3
import tempfile

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django  # noqa: E402

django.setup()

from django.test import TestCase  # noqa: E402

from apps.accounts.models import User  # noqa: E402
from apps.audio.models import Character, NarrationScript, ScriptSegment  # noqa: E402
from apps.player.models import PlaybackState  # noqa: E402
from apps.stories.models import AppSetting, Story, StoryFolder, StoryFolderMembership, StoryView  # noqa: E402
from scripts.migrate_from_v1 import run_migration  # noqa: E402

# Sample script_json matching the v1 NarrationScript Pydantic model
SAMPLE_SCRIPT_JSON = json.dumps(
    {
        "title": "The Haunted House",
        "characters": {
            "narrator": {"voice_profile": "deep, steady, ominous", "voice_id": "voice_abc123"},
            "Sarah": {"voice_profile": "young, female, fearful", "voice_id": None},
        },
        "segments": [
            {"type": "ambient", "description": "rain on tin roof", "loop": True},
            {
                "type": "narration",
                "character": "narrator",
                "text": "I moved into the house last week.",
                "tone": "foreboding",
            },
            {"type": "sfx", "description": "door creaking slowly"},
            {
                "type": "dialogue",
                "character": "Sarah",
                "text": "Did you hear that?",
                "tone": "panicked whisper",
            },
            {"type": "pause", "duration_ms": 1500},
        ],
    }
)

SAMPLE_SERIES_JSON = json.dumps(
    [
        {"title": "Part 1", "url": "https://reddit.com/1", "id": "abc123", "part_number": 1, "created_utc": 1609459200.0},
        {"title": "Part 2", "url": "https://reddit.com/2", "id": "def456", "part_number": 2, "created_utc": 1609545600.0},
    ]
)


def create_v1_database(db_path: str) -> None:
    """Create a v1-format SQLite database with sample data."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tables matching v1 SQLAlchemy schema
    cursor.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            is_admin BOOLEAN DEFAULT 0
        );

        CREATE TABLE stories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            reddit_url TEXT UNIQUE,
            text_content TEXT NOT NULL,
            narration_text TEXT,
            script_json TEXT,
            content_hash TEXT NOT NULL,
            author TEXT,
            audio_file_path TEXT,
            part_count INTEGER DEFAULT 1,
            series_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE playback_states (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            story_id INTEGER NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
            position_seconds FLOAT DEFAULT 0.0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, story_id)
        );

        CREATE TABLE story_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            story_id INTEGER NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
            viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            hidden BOOLEAN DEFAULT 0,
            UNIQUE(user_id, story_id)
        );

        CREATE TABLE story_folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, name)
        );

        CREATE TABLE story_folder_memberships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folder_id INTEGER NOT NULL REFERENCES story_folders(id) ON DELETE CASCADE,
            story_id INTEGER NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(folder_id, story_id)
        );

        CREATE TABLE app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """
    )

    # Insert sample data
    cursor.execute(
        "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)",
        ("testuser", "$2b$12$abcdefghijklmnopqrstuuABCDEFGHIJKLMNOPQRSTUVWXYZ012", 0),
    )
    cursor.execute(
        "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)",
        ("admin", "$2b$12$xyzxyzxyzxyzxyzxyzxyzuuABCDEFGHIJKLMNOPQRSTUVWXYZ012", 1),
    )

    cursor.execute(
        "INSERT INTO stories (title, reddit_url, text_content, narration_text, script_json, "
        "content_hash, author, audio_file_path, part_count, series_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "The Haunted House",
            "https://reddit.com/r/nosleep/comments/abc/haunted/",
            "I moved into the house last week.",
            "I moved into the house last week.",
            SAMPLE_SCRIPT_JSON,
            "abc123hash",
            "spookyauthor",
            "./data/stories/uuid-1.mp3",
            2,
            SAMPLE_SERIES_JSON,
        ),
    )
    cursor.execute(
        "INSERT INTO stories (title, text_content, content_hash, author) VALUES (?, ?, ?, ?)",
        ("No Script Story", "Just some text.", "def456hash", "otherauthor"),
    )

    cursor.execute(
        "INSERT INTO playback_states (user_id, story_id, position_seconds) VALUES (?, ?, ?)",
        (1, 1, 42.5),
    )

    cursor.execute(
        "INSERT INTO story_views (user_id, story_id, hidden) VALUES (?, ?, ?)",
        (1, 1, 0),
    )
    cursor.execute(
        "INSERT INTO story_views (user_id, story_id, hidden) VALUES (?, ?, ?)",
        (2, 1, 1),
    )

    cursor.execute(
        "INSERT INTO story_folders (user_id, name) VALUES (?, ?)",
        (1, "Favorites"),
    )
    cursor.execute(
        "INSERT INTO story_folder_memberships (folder_id, story_id) VALUES (?, ?)",
        (1, 1),
    )
    cursor.execute(
        "INSERT INTO story_folder_memberships (folder_id, story_id) VALUES (?, ?)",
        (1, 2),
    )

    cursor.execute("INSERT INTO app_settings (key, value) VALUES (?, ?)", ("cache_ttl", "3600"))
    cursor.execute("INSERT INTO app_settings (key, value) VALUES (?, ?)", ("voice_notes", "Use deep voices"))

    conn.commit()
    conn.close()


class MigrationScriptTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        create_v1_database(self.tmp.name)

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_full_migration(self):
        result = run_migration(self.tmp.name)

        assert result["users"] == 2
        assert result["stories"] == 2
        assert result["scripts"] == 1
        assert result["characters"] == 2
        assert result["segments"] == 5
        assert result["playback_states"] == 1
        assert result["story_views"] == 2
        assert result["folders"] == 1
        assert result["memberships"] == 2
        assert result["app_settings"] == 2

    def test_user_migration(self):
        run_migration(self.tmp.name)

        testuser = User.objects.get(username="testuser")
        assert not testuser.is_staff
        assert not testuser.is_superuser
        # Password should be prefixed with bcrypt$ for Django compatibility
        assert testuser.password.startswith("bcrypt$")

        admin = User.objects.get(username="admin")
        assert admin.is_staff
        assert admin.is_superuser

    def test_story_migration(self):
        run_migration(self.tmp.name)

        story = Story.objects.get(content_hash="abc123hash")
        assert story.title == "The Haunted House"
        assert story.reddit_url == "https://reddit.com/r/nosleep/comments/abc/haunted/"
        assert story.author == "spookyauthor"
        assert story.audio_file_path == "./data/stories/uuid-1.mp3"
        assert story.part_count == 2

    def test_series_json_migration(self):
        run_migration(self.tmp.name)

        story = Story.objects.get(content_hash="abc123hash")
        assert isinstance(story.series_json, list)
        assert len(story.series_json) == 2
        assert story.series_json[0]["title"] == "Part 1"
        assert story.series_json[1]["part_number"] == 2

    def test_script_decomposition(self):
        run_migration(self.tmp.name)

        story = Story.objects.get(content_hash="abc123hash")
        script = story.script
        assert script.title == "The Haunted House"

        # Verify characters
        characters = {c.name: c for c in script.characters.all()}
        assert "narrator" in characters
        assert "Sarah" in characters
        assert characters["narrator"].voice_profile == "deep, steady, ominous"
        assert characters["narrator"].voice_id == "voice_abc123"
        assert characters["Sarah"].voice_profile == "young, female, fearful"
        assert characters["Sarah"].voice_id == ""  # None converted to ""

    def test_segment_decomposition(self):
        run_migration(self.tmp.name)

        story = Story.objects.get(content_hash="abc123hash")
        segments = list(story.script.segments.all())
        assert len(segments) == 5

        # Segment 0: ambient
        assert segments[0].type == "ambient"
        assert segments[0].description == "rain on tin roof"
        assert segments[0].loop is True
        assert segments[0].character is None

        # Segment 1: narration with character FK
        assert segments[1].type == "narration"
        assert segments[1].text == "I moved into the house last week."
        assert segments[1].tone == "foreboding"
        assert segments[1].character.name == "narrator"

        # Segment 2: sfx
        assert segments[2].type == "sfx"
        assert segments[2].description == "door creaking slowly"

        # Segment 3: dialogue with character FK
        assert segments[3].type == "dialogue"
        assert segments[3].character.name == "Sarah"
        assert segments[3].text == "Did you hear that?"

        # Segment 4: pause
        assert segments[4].type == "pause"
        assert segments[4].duration_ms == 1500

    def test_story_without_script(self):
        run_migration(self.tmp.name)

        story = Story.objects.get(content_hash="def456hash")
        assert story.title == "No Script Story"
        assert not hasattr(story, "script") or not NarrationScript.objects.filter(story=story).exists()

    def test_playback_state_migration(self):
        run_migration(self.tmp.name)

        state = PlaybackState.objects.first()
        assert state.position_seconds == 42.5
        assert state.user.username == "testuser"

    def test_story_views_migration(self):
        run_migration(self.tmp.name)

        views = StoryView.objects.all()
        assert views.count() == 2

        hidden_view = StoryView.objects.get(hidden=True)
        assert hidden_view.user.username == "admin"

    def test_folders_migration(self):
        run_migration(self.tmp.name)

        folder = StoryFolder.objects.first()
        assert folder.name == "Favorites"
        assert folder.user.username == "testuser"
        assert folder.stories.count() == 2

    def test_app_settings_migration(self):
        run_migration(self.tmp.name)

        assert AppSetting.get("cache_ttl") == "3600"
        assert AppSetting.get("voice_notes") == "Use deep voices"

    def test_missing_db_raises_error(self):
        with self.assertRaises(FileNotFoundError):
            run_migration("/nonexistent/path/db.sqlite3")

    def test_migration_is_atomic(self):
        """If migration fails mid-way, no partial data should be committed."""
        # Pre-create a Django user that will clash with a v1 user during migration,
        # causing an IntegrityError after some records are already processed.
        User.objects.create_user(username="testuser", password="existing")

        with self.assertRaises(Exception):
            run_migration(self.tmp.name)

        # The pre-existing user should still be there, but no v1 data should have
        # been committed (the transaction should have rolled back).
        assert User.objects.count() == 1  # only the pre-existing one
        assert Story.objects.count() == 0
