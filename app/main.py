import os
import sqlite3
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from .database import engine, SQLALCHEMY_DATABASE_URL
from .models import story, app_setting  # load all models to register them with Base
from .routers import audio, stories, player, auth, settings


def _migrate_db():
    """Add any columns that exist in the ORM models but are missing from the
    actual SQLite database.  ``create_all`` only creates *tables* — it never
    adds new columns to existing tables."""
    if not SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
        return

    db_path = SQLALCHEMY_DATABASE_URL.replace("sqlite:///", "")
    if not os.path.exists(db_path):
        return  # fresh DB — create_all will handle everything

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute("PRAGMA table_info(stories)")
        existing_cols = {row[1] for row in cursor.fetchall()}

        # Columns that may be missing from older databases.
        # Each entry: (column_name, SQL type + constraints)
        new_columns = [
            ("content_hash", "TEXT NOT NULL DEFAULT ''"),
            ("author", "TEXT"),
            ("part_count", "INTEGER DEFAULT 1"),
            ("series_json", "TEXT"),
        ]

        for col_name, col_def in new_columns:
            if col_name not in existing_cols:
                conn.execute(
                    f"ALTER TABLE stories ADD COLUMN {col_name} {col_def}"
                )

        conn.commit()
    finally:
        conn.close()


_migrate_db()
story.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Voice To The Dark", version="0.1.0")

# Static files (icons for lock-screen artwork, etc.)
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# API routers
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(audio.router, prefix="/audio", tags=["audio"])
app.include_router(stories.router, prefix="/stories", tags=["stories"])

app.include_router(settings.router, prefix="/settings", tags=["settings"])

# Web UI (player pages served at the root)
app.include_router(player.router, tags=["player"])
