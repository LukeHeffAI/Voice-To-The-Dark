#!/usr/bin/env python
"""
Migrate data from legacy FastAPI SQLite DB (horror_narrator.db) to new Django DB.

Usage:
    python scripts/migrate_from_v1.py [--legacy-db path/to/horror_narrator.db] [--dry-run]
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

# Bootstrap Django
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.db import connection, transaction  # noqa: E402

from apps.accounts.models import User  # noqa: E402
from apps.player.models import PlaybackState  # noqa: E402
from apps.stories.models import AppSetting, Story, StoryFolder, StoryFolderMembership, StoryView  # noqa: E402

DEFAULT_LEGACY_DB = Path(__file__).resolve().parent.parent / "data" / "db" / "horror_narrator.db"


def migrate_users(cursor):
    """Migrate users, preserving IDs and bcrypt password hashes."""
    cursor.execute("SELECT id, username, password_hash, is_admin FROM users")
    rows = cursor.fetchall()
    users = []
    for row in rows:
        user_id, username, password_hash, is_admin = row
        users.append(
            User(
                id=user_id,
                username=username,
                # Prefix bcrypt hash for Django's BCryptPasswordHasher
                password=f"bcrypt${password_hash}",
                is_admin=bool(is_admin),
                is_staff=bool(is_admin),
                is_superuser=bool(is_admin),
            )
        )
    User.objects.bulk_create(users)
    return len(users)


def migrate_stories(cursor):
    """Migrate stories, parsing JSON text fields into proper JSONField values."""
    cursor.execute(
        "SELECT id, title, reddit_url, text_content, narration_text, "
        "script_json, content_hash, author, audio_file_path, "
        "part_count, series_json, created_at, updated_at FROM stories"
    )
    stories = []
    timestamps = []
    for row in cursor.fetchall():
        (
            story_id,
            title,
            reddit_url,
            text_content,
            narration_text,
            script_json,
            content_hash,
            author,
            audio_file_path,
            part_count,
            series_json,
            created_at,
            updated_at,
        ) = row

        parsed_script = None
        if script_json:
            try:
                parsed_script = json.loads(script_json)
            except json.JSONDecodeError:
                print(f"  WARNING: Invalid script_json for story {story_id}, setting to null")

        parsed_series = None
        if series_json:
            try:
                parsed_series = json.loads(series_json)
            except json.JSONDecodeError:
                print(f"  WARNING: Invalid series_json for story {story_id}, setting to null")

        stories.append(
            Story(
                id=story_id,
                title=title,
                reddit_url=reddit_url or None,
                text_content=text_content,
                narration_text=narration_text,
                script_json=parsed_script,
                content_hash=content_hash or "",
                author=author,
                audio_file_path=audio_file_path,
                part_count=part_count or 1,
                series_json=parsed_series,
            )
        )
        timestamps.append((story_id, created_at, updated_at))

    Story.objects.bulk_create(stories)

    # Restore original timestamps (auto_now_add/auto_now overrides them)
    with connection.cursor() as c:
        for story_id, created_at, updated_at in timestamps:
            if created_at or updated_at:
                c.execute(
                    "UPDATE stories SET created_at = COALESCE(?, created_at), "
                    "updated_at = COALESCE(?, updated_at) WHERE id = ?",
                    [created_at, updated_at, story_id],
                )

    return len(stories)


def migrate_playback_states(cursor):
    """Migrate playback states."""
    cursor.execute("SELECT id, user_id, story_id, position_seconds, updated_at FROM playback_states")
    states = []
    timestamps = []
    for row in cursor.fetchall():
        state_id, user_id, story_id, position_seconds, updated_at = row
        states.append(
            PlaybackState(
                id=state_id,
                user_id=user_id,
                story_id=story_id,
                position_seconds=position_seconds or 0.0,
            )
        )
        timestamps.append((state_id, updated_at))

    PlaybackState.objects.bulk_create(states)

    with connection.cursor() as c:
        for state_id, updated_at in timestamps:
            if updated_at:
                c.execute(
                    "UPDATE playback_states SET updated_at = ? WHERE id = ?",
                    [updated_at, state_id],
                )

    return len(states)


def migrate_story_views(cursor):
    """Migrate story views."""
    cursor.execute("SELECT id, user_id, story_id, viewed_at, hidden FROM story_views")
    views = []
    timestamps = []
    for row in cursor.fetchall():
        view_id, user_id, story_id, viewed_at, hidden = row
        views.append(
            StoryView(
                id=view_id,
                user_id=user_id,
                story_id=story_id,
                hidden=bool(hidden),
            )
        )
        timestamps.append((view_id, viewed_at))

    StoryView.objects.bulk_create(views)

    with connection.cursor() as c:
        for view_id, viewed_at in timestamps:
            if viewed_at:
                c.execute(
                    "UPDATE story_views SET viewed_at = ? WHERE id = ?",
                    [viewed_at, view_id],
                )

    return len(views)


def migrate_folders(cursor):
    """Migrate story folders."""
    cursor.execute("SELECT id, user_id, name, created_at FROM story_folders")
    folders = []
    timestamps = []
    for row in cursor.fetchall():
        folder_id, user_id, name, created_at = row
        folders.append(
            StoryFolder(
                id=folder_id,
                user_id=user_id,
                name=name,
            )
        )
        timestamps.append((folder_id, created_at))

    StoryFolder.objects.bulk_create(folders)

    with connection.cursor() as c:
        for folder_id, created_at in timestamps:
            if created_at:
                c.execute(
                    "UPDATE story_folders SET created_at = ? WHERE id = ?",
                    [created_at, folder_id],
                )

    return len(folders)


def migrate_folder_memberships(cursor):
    """Migrate folder memberships."""
    cursor.execute("SELECT id, folder_id, story_id, added_at FROM story_folder_memberships")
    memberships = []
    timestamps = []
    for row in cursor.fetchall():
        mem_id, folder_id, story_id, added_at = row
        memberships.append(
            StoryFolderMembership(
                id=mem_id,
                folder_id=folder_id,
                story_id=story_id,
            )
        )
        timestamps.append((mem_id, added_at))

    StoryFolderMembership.objects.bulk_create(memberships)

    with connection.cursor() as c:
        for mem_id, added_at in timestamps:
            if added_at:
                c.execute(
                    "UPDATE story_folder_memberships SET added_at = ? WHERE id = ?",
                    [added_at, mem_id],
                )

    return len(memberships)


def migrate_app_settings(cursor):
    """Migrate app settings."""
    cursor.execute("SELECT key, value, updated_at FROM app_settings")
    settings_list = []
    for row in cursor.fetchall():
        key, value, updated_at = row
        settings_list.append(AppSetting(key=key, value=value))
    AppSetting.objects.bulk_create(settings_list)
    return len(settings_list)


def main():
    parser = argparse.ArgumentParser(description="Migrate V1 data to Django DB")
    parser.add_argument("--legacy-db", type=Path, default=DEFAULT_LEGACY_DB)
    parser.add_argument("--dry-run", action="store_true", help="Run migration in a transaction and roll back")
    args = parser.parse_args()

    if not args.legacy_db.exists():
        print(f"ERROR: Legacy database not found at {args.legacy_db}")
        print("Provide the path with --legacy-db or place it at data/db/horror_narrator.db")
        sys.exit(1)

    print(f"Migrating from: {args.legacy_db}")

    conn = sqlite3.connect(str(args.legacy_db))
    legacy = conn.cursor()

    migration_steps = [
        ("Users", migrate_users),
        ("Stories", migrate_stories),
        ("Playback States", migrate_playback_states),
        ("Story Views", migrate_story_views),
        ("Folders", migrate_folders),
        ("Folder Memberships", migrate_folder_memberships),
        ("App Settings", migrate_app_settings),
    ]

    try:
        with transaction.atomic():
            for name, func in migration_steps:
                count = func(legacy)
                print(f"  Migrated {count} {name}")

            if args.dry_run:
                print("\n  DRY RUN -- rolling back all changes")
                transaction.set_rollback(True)
    except Exception as e:
        print(f"\nERROR: Migration failed: {e}")
        raise
    finally:
        conn.close()

    if not args.dry_run:
        print("\nMigration complete!")


if __name__ == "__main__":
    main()
