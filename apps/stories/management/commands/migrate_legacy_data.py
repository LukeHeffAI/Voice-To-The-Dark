"""Migrate data from the legacy FastAPI SQLite database to Django.

Reads the old horror_narrator.db and imports users, stories, playback
states, story views, folders, folder memberships, and app settings into
the Django database. Preserves primary key IDs to maintain referential
integrity.

Usage:
    python manage.py migrate_legacy_data
    python manage.py migrate_legacy_data --db /path/to/horror_narrator.db
    python manage.py migrate_legacy_data --dry-run
"""

import json
import sqlite3
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection

from apps.accounts.models import User
from apps.player.models import PlaybackState
from apps.stories.models import AppSetting, Story, StoryFolder, StoryFolderMembership, StoryView


class Command(BaseCommand):
    help = "Migrate data from the legacy FastAPI SQLite database to Django."

    def add_arguments(self, parser):
        parser.add_argument(
            "--db",
            type=str,
            default=str(settings.DATA_DIR / "db" / "horror_narrator.db"),
            help="Path to the legacy SQLite database (default: data/db/horror_narrator.db)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview what would be migrated without writing to the database.",
        )

    def handle(self, *args, **options):
        db_path = options["db"]
        dry_run = options["dry_run"]

        if not Path(db_path).exists():
            self.stderr.write(self.style.ERROR(f"Legacy database not found: {db_path}"))
            return

        self.stdout.write(f"Opening legacy database: {db_path}")
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no data will be written"))

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        try:
            counts = {}
            counts["users"] = self._migrate_users(conn, dry_run)
            counts["stories"] = self._migrate_stories(conn, dry_run)
            counts["playback_states"] = self._migrate_playback_states(conn, dry_run)
            counts["story_views"] = self._migrate_story_views(conn, dry_run)
            counts["story_folders"] = self._migrate_story_folders(conn, dry_run)
            counts["story_folder_memberships"] = self._migrate_folder_memberships(conn, dry_run)
            counts["app_settings"] = self._migrate_app_settings(conn, dry_run)

            # Reset auto-increment sequences for SQLite
            if not dry_run:
                self._reset_sequences()

            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("Migration summary:"))
            for table, count in counts.items():
                self.stdout.write(f"  {table}: {count} records")
        finally:
            conn.close()

    def _migrate_users(self, conn, dry_run):
        rows = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
        self.stdout.write(f"Found {len(rows)} users")

        if dry_run:
            for row in rows:
                self.stdout.write(f"  [DRY RUN] User: {row['username']} (admin={row['is_admin']})")
            return len(rows)

        count = 0
        for row in rows:
            if User.objects.filter(id=row["id"]).exists():
                self.stdout.write(f"  Skipping user {row['username']} (ID {row['id']} already exists)")
                continue

            # Convert bcrypt hash to Django format: bcrypt$$<hash>
            password_hash = row["password_hash"]
            if password_hash and password_hash.startswith("$2"):
                password_hash = f"bcrypt$${password_hash}"

            user = User(
                id=row["id"],
                username=row["username"],
                password=password_hash,
                is_admin=bool(row["is_admin"]),
                is_staff=bool(row["is_admin"]),
                is_active=True,
            )
            user.save()
            count += 1
            self.stdout.write(f"  Migrated user: {row['username']}")

        return count

    def _migrate_stories(self, conn, dry_run):
        rows = conn.execute("SELECT * FROM stories ORDER BY id").fetchall()
        self.stdout.write(f"Found {len(rows)} stories")

        if dry_run:
            for row in rows:
                self.stdout.write(f"  [DRY RUN] Story: {row['title'][:60]}")
            return len(rows)

        count = 0
        for row in rows:
            if Story.objects.filter(id=row["id"]).exists():
                self.stdout.write(f"  Skipping story ID {row['id']} (already exists)")
                continue

            # Parse JSON fields from TEXT to Python objects
            script_json = self._parse_json(row["script_json"])
            series_json = self._parse_json(row["series_json"])

            story = Story(
                id=row["id"],
                title=row["title"],
                reddit_url=row["reddit_url"],
                text_content=row["text_content"],
                narration_text=row["narration_text"],
                script_json=script_json,
                content_hash=row["content_hash"],
                author=row["author"],
                audio_file_path=row["audio_file_path"],
                part_count=row["part_count"] or 1,
                series_json=series_json,
            )
            story.save()
            count += 1

        self.stdout.write(f"  Migrated {count} stories")
        return count

    def _migrate_playback_states(self, conn, dry_run):
        rows = conn.execute("SELECT * FROM playback_states ORDER BY id").fetchall()
        self.stdout.write(f"Found {len(rows)} playback states")

        if dry_run:
            return len(rows)

        count = 0
        for row in rows:
            if PlaybackState.objects.filter(id=row["id"]).exists():
                continue
            try:
                PlaybackState.objects.create(
                    id=row["id"],
                    user_id=row["user_id"],
                    story_id=row["story_id"],
                    position_seconds=row["position_seconds"] or 0.0,
                )
                count += 1
            except Exception as e:
                self.stderr.write(f"  Error migrating playback state {row['id']}: {e}")

        self.stdout.write(f"  Migrated {count} playback states")
        return count

    def _migrate_story_views(self, conn, dry_run):
        # Check if the table exists (may not in older DBs)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        if "story_views" not in tables:
            self.stdout.write("  No story_views table found, skipping")
            return 0

        rows = conn.execute("SELECT * FROM story_views ORDER BY id").fetchall()
        self.stdout.write(f"Found {len(rows)} story views")

        if dry_run:
            return len(rows)

        count = 0
        for row in rows:
            if StoryView.objects.filter(id=row["id"]).exists():
                continue
            try:
                StoryView.objects.create(
                    id=row["id"],
                    user_id=row["user_id"],
                    story_id=row["story_id"],
                    hidden=bool(row["hidden"]),
                )
                count += 1
            except Exception as e:
                self.stderr.write(f"  Error migrating story view {row['id']}: {e}")

        self.stdout.write(f"  Migrated {count} story views")
        return count

    def _migrate_story_folders(self, conn, dry_run):
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        if "story_folders" not in tables:
            self.stdout.write("  No story_folders table found, skipping")
            return 0

        rows = conn.execute("SELECT * FROM story_folders ORDER BY id").fetchall()
        self.stdout.write(f"Found {len(rows)} story folders")

        if dry_run:
            return len(rows)

        count = 0
        for row in rows:
            if StoryFolder.objects.filter(id=row["id"]).exists():
                continue
            try:
                StoryFolder.objects.create(
                    id=row["id"],
                    user_id=row["user_id"],
                    name=row["name"],
                )
                count += 1
            except Exception as e:
                self.stderr.write(f"  Error migrating folder {row['id']}: {e}")

        self.stdout.write(f"  Migrated {count} folders")
        return count

    def _migrate_folder_memberships(self, conn, dry_run):
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        if "story_folder_memberships" not in tables:
            self.stdout.write("  No story_folder_memberships table found, skipping")
            return 0

        rows = conn.execute("SELECT * FROM story_folder_memberships ORDER BY id").fetchall()
        self.stdout.write(f"Found {len(rows)} folder memberships")

        if dry_run:
            return len(rows)

        count = 0
        for row in rows:
            if StoryFolderMembership.objects.filter(id=row["id"]).exists():
                continue
            try:
                StoryFolderMembership.objects.create(
                    id=row["id"],
                    folder_id=row["folder_id"],
                    story_id=row["story_id"],
                )
                count += 1
            except Exception as e:
                self.stderr.write(f"  Error migrating membership {row['id']}: {e}")

        self.stdout.write(f"  Migrated {count} memberships")
        return count

    def _migrate_app_settings(self, conn, dry_run):
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        if "app_settings" not in tables:
            self.stdout.write("  No app_settings table found, skipping")
            return 0

        rows = conn.execute("SELECT * FROM app_settings").fetchall()
        self.stdout.write(f"Found {len(rows)} app settings")

        if dry_run:
            for row in rows:
                self.stdout.write(f"  [DRY RUN] Setting: {row['key']}={row['value'][:50]}")
            return len(rows)

        count = 0
        for row in rows:
            AppSetting.set(row["key"], row["value"])
            count += 1

        self.stdout.write(f"  Migrated {count} settings")
        return count

    def _parse_json(self, value):
        """Parse a JSON string to a Python object, or return None."""
        if not value:
            return None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None

    def _reset_sequences(self):
        """Reset SQLite auto-increment sequences to avoid ID collisions."""
        if connection.vendor != "sqlite":
            return

        with connection.cursor() as cursor:
            # Get the max ID for each table and update sqlite_sequence
            tables = [
                ("auth_user", User),
                ("stories", Story),
                ("playback_states", PlaybackState),
                ("story_views", StoryView),
                ("story_folders", StoryFolder),
                ("story_folder_memberships", StoryFolderMembership),
            ]
            for table_name, model in tables:
                max_id = model.objects.order_by("-id").values_list("id", flat=True).first()
                if max_id:
                    cursor.execute(
                        "INSERT OR REPLACE INTO sqlite_sequence (name, seq) VALUES (%s, %s)",
                        [table_name, max_id],
                    )
