"""
Migrate data from the legacy FastAPI/SQLAlchemy SQLite database to the new Django schema.

Usage:
    DJANGO_SETTINGS_MODULE=config.settings.development python scripts/migrate_from_v1.py [path_to_v1_db]

Default v1 DB path: data/db/stories.db
"""

import json
import os
import sqlite3
import sys
from pathlib import Path

# Set up Django before importing models
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.db import transaction  # noqa: E402

from apps.accounts.models import User  # noqa: E402
from apps.audio.models import Character, NarrationScript, ScriptSegment  # noqa: E402
from apps.player.models import PlaybackState  # noqa: E402
from apps.stories.models import AppSetting, Story, StoryFolder, StoryFolderMembership, StoryView  # noqa: E402


def get_v1_connection(db_path: str) -> sqlite3.Connection:
    """Open a read-only connection to the v1 SQLite database."""
    if not Path(db_path).exists():
        raise FileNotFoundError(f"V1 database not found at: {db_path}")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def migrate_users(conn: sqlite3.Connection) -> dict[int, int]:
    """Migrate v1 users to Django User model. Returns mapping of old_id -> new_id."""
    cursor = conn.execute("SELECT id, username, password_hash, is_admin FROM users")
    rows = cursor.fetchall()
    id_map = {}

    for row in rows:
        # Django stores passwords as <algorithm>$<hash>. For bcrypt hashes from v1,
        # prefix with "bcrypt$" so Django's BCryptPasswordHasher can verify them.
        password = row["password_hash"]
        if password and not password.startswith(("bcrypt$", "pbkdf2_sha256$")):
            password = f"bcrypt${password}"

        user = User(
            username=row["username"],
            password=password,
            is_staff=bool(row["is_admin"]),
            is_superuser=bool(row["is_admin"]),
        )
        user.save()
        id_map[row["id"]] = user.pk

    return id_map


def migrate_stories(conn: sqlite3.Connection) -> dict[int, int]:
    """Migrate v1 stories to Django Story model. Returns mapping of old_id -> new_id."""
    cursor = conn.execute(
        "SELECT id, title, reddit_url, text_content, narration_text, "
        "content_hash, author, audio_file_path, part_count, series_json, "
        "created_at, updated_at FROM stories"
    )
    rows = cursor.fetchall()
    id_map = {}

    for row in rows:
        # Parse series_json from text to Python object for Django JSONField
        series_data = None
        if row["series_json"]:
            try:
                series_data = json.loads(row["series_json"])
            except (json.JSONDecodeError, TypeError):
                pass

        story = Story(
            title=row["title"],
            reddit_url=row["reddit_url"] or None,
            text_content=row["text_content"],
            narration_text=row["narration_text"] or "",
            content_hash=row["content_hash"],
            author=row["author"] or "",
            audio_file_path=row["audio_file_path"] or "",
            part_count=row["part_count"] or 1,
            series_json=series_data,
        )
        story.save()
        id_map[row["id"]] = story.pk

    return id_map


def migrate_scripts(conn: sqlite3.Connection, story_id_map: dict[int, int]) -> int:
    """Decompose script_json blobs into NarrationScript, Character, and ScriptSegment rows.

    Returns count of scripts migrated.
    """
    cursor = conn.execute("SELECT id, title, script_json FROM stories WHERE script_json IS NOT NULL")
    rows = cursor.fetchall()
    count = 0

    for row in rows:
        old_story_id = row["id"]
        new_story_id = story_id_map.get(old_story_id)
        if new_story_id is None:
            continue

        try:
            script_data = json.loads(row["script_json"])
        except (json.JSONDecodeError, TypeError):
            continue

        # Create NarrationScript
        script = NarrationScript.objects.create(
            story_id=new_story_id,
            title=script_data.get("title", row["title"]),
        )

        # Create Characters
        char_map = {}  # name -> Character instance
        characters = script_data.get("characters", {})
        for char_name, char_data in characters.items():
            char = Character.objects.create(
                script=script,
                name=char_name,
                voice_profile=char_data.get("voice_profile", ""),
                voice_id=char_data.get("voice_id", "") or "",
            )
            char_map[char_name] = char

        # Create ScriptSegments
        segments = script_data.get("segments", [])
        for idx, seg_data in enumerate(segments):
            # Link character FK by name lookup
            character = None
            char_name = seg_data.get("character")
            if char_name and char_name in char_map:
                character = char_map[char_name]

            ScriptSegment.objects.create(
                script=script,
                order=idx,
                type=seg_data.get("type", "narration"),
                character=character,
                text=seg_data.get("text", "") or "",
                tone=seg_data.get("tone", "") or "",
                description=seg_data.get("description", "") or "",
                duration_ms=seg_data.get("duration_ms"),
                loop=seg_data.get("loop", False),
            )

        count += 1

    return count


def migrate_playback_states(
    conn: sqlite3.Connection, user_id_map: dict[int, int], story_id_map: dict[int, int]
) -> int:
    """Migrate playback states. Returns count migrated."""
    cursor = conn.execute("SELECT user_id, story_id, position_seconds FROM playback_states")
    rows = cursor.fetchall()
    count = 0

    for row in rows:
        new_user_id = user_id_map.get(row["user_id"])
        new_story_id = story_id_map.get(row["story_id"])
        if new_user_id is None or new_story_id is None:
            continue

        PlaybackState.objects.create(
            user_id=new_user_id,
            story_id=new_story_id,
            position_seconds=row["position_seconds"] or 0.0,
        )
        count += 1

    return count


def migrate_story_views(
    conn: sqlite3.Connection, user_id_map: dict[int, int], story_id_map: dict[int, int]
) -> int:
    """Migrate story views. Returns count migrated."""
    cursor = conn.execute("SELECT user_id, story_id, hidden FROM story_views")
    rows = cursor.fetchall()
    count = 0

    for row in rows:
        new_user_id = user_id_map.get(row["user_id"])
        new_story_id = story_id_map.get(row["story_id"])
        if new_user_id is None or new_story_id is None:
            continue

        StoryView.objects.create(
            user_id=new_user_id,
            story_id=new_story_id,
            hidden=bool(row["hidden"]),
        )
        count += 1

    return count


def migrate_folders(
    conn: sqlite3.Connection, user_id_map: dict[int, int], story_id_map: dict[int, int]
) -> tuple[int, int]:
    """Migrate folders and memberships. Returns (folder_count, membership_count)."""
    # Migrate folders
    cursor = conn.execute("SELECT id, user_id, name FROM story_folders")
    rows = cursor.fetchall()
    folder_id_map = {}
    folder_count = 0

    for row in rows:
        new_user_id = user_id_map.get(row["user_id"])
        if new_user_id is None:
            continue

        folder = StoryFolder.objects.create(
            user_id=new_user_id,
            name=row["name"],
        )
        folder_id_map[row["id"]] = folder.pk
        folder_count += 1

    # Migrate memberships
    cursor = conn.execute("SELECT folder_id, story_id FROM story_folder_memberships")
    rows = cursor.fetchall()
    membership_count = 0

    for row in rows:
        new_folder_id = folder_id_map.get(row["folder_id"])
        new_story_id = story_id_map.get(row["story_id"])
        if new_folder_id is None or new_story_id is None:
            continue

        StoryFolderMembership.objects.create(
            folder_id=new_folder_id,
            story_id=new_story_id,
        )
        membership_count += 1

    return folder_count, membership_count


def migrate_app_settings(conn: sqlite3.Connection) -> int:
    """Migrate app settings. Returns count migrated."""
    cursor = conn.execute("SELECT key, value FROM app_settings")
    rows = cursor.fetchall()
    count = 0

    for row in rows:
        AppSetting.objects.create(key=row["key"], value=row["value"])
        count += 1

    return count


def run_migration(v1_db_path: str) -> dict[str, int]:
    """Run the full migration inside a transaction. Returns summary counts."""
    conn = get_v1_connection(v1_db_path)

    try:
        with transaction.atomic():
            print(f"Migrating from: {v1_db_path}")

            user_id_map = migrate_users(conn)
            print(f"  Users: {len(user_id_map)}")

            story_id_map = migrate_stories(conn)
            print(f"  Stories: {len(story_id_map)}")

            script_count = migrate_scripts(conn, story_id_map)
            print(f"  Scripts decomposed: {script_count}")
            print(f"    Characters: {Character.objects.count()}")
            print(f"    Segments: {ScriptSegment.objects.count()}")

            playback_count = migrate_playback_states(conn, user_id_map, story_id_map)
            print(f"  Playback states: {playback_count}")

            view_count = migrate_story_views(conn, user_id_map, story_id_map)
            print(f"  Story views: {view_count}")

            folder_count, membership_count = migrate_folders(conn, user_id_map, story_id_map)
            print(f"  Folders: {folder_count}")
            print(f"  Folder memberships: {membership_count}")

            settings_count = migrate_app_settings(conn)
            print(f"  App settings: {settings_count}")

            print("\nMigration complete!")

            return {
                "users": len(user_id_map),
                "stories": len(story_id_map),
                "scripts": script_count,
                "characters": Character.objects.count(),
                "segments": ScriptSegment.objects.count(),
                "playback_states": playback_count,
                "story_views": view_count,
                "folders": folder_count,
                "memberships": membership_count,
                "app_settings": settings_count,
            }
    finally:
        conn.close()


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent.parent
    default_path = str(base_dir / "data" / "db" / "stories.db")

    # Also check the alternative v1 database name
    if not Path(default_path).exists():
        alt_path = str(base_dir / "data" / "db" / "horror_narrator.db")
        if Path(alt_path).exists():
            default_path = alt_path

    db_path = sys.argv[1] if len(sys.argv) > 1 else default_path

    run_migration(db_path)
