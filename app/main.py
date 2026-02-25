import logging
import os
import sqlite3
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from .database import engine, SQLALCHEMY_DATABASE_URL
from .models import story, app_setting  # load all models to register them with Base
from .routers import audio, stories, player, auth, settings

logger = logging.getLogger(__name__)


def _migrate_db():
    """Auto-migrate all ORM tables so the SQLite schema matches the models.

    SQLAlchemy's ``create_all`` only creates *tables* — it never adds new
    columns to existing tables.  This function inspects every registered model
    and ADDs any columns that are defined in code but missing from the
    database, preventing 'no such column' errors at runtime.
    """
    if not SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
        return

    db_path = SQLALCHEMY_DATABASE_URL.replace("sqlite:///", "")
    if not os.path.exists(db_path):
        return  # fresh DB — create_all will handle everything

    conn = sqlite3.connect(db_path)
    try:
        for table in story.Base.metadata.sorted_tables:
            cursor = conn.execute(f"PRAGMA table_info({table.name})")
            existing_cols = {row[1] for row in cursor.fetchall()}
            if not existing_cols:
                continue  # table doesn't exist yet; create_all will make it

            for column in table.columns:
                if column.name in existing_cols or column.primary_key:
                    continue

                col_type = column.type.compile(dialect=engine.dialect)
                stmt = f"ALTER TABLE {table.name} ADD COLUMN {column.name} {col_type}"

                # Determine DEFAULT clause from model metadata
                default_sql = None
                if column.server_default is not None:
                    compiled = column.server_default.arg.compile(
                        dialect=engine.dialect
                    )
                    default_sql = str(compiled)
                elif column.default is not None:
                    arg = column.default.arg
                    if not callable(arg):
                        if isinstance(arg, bool):
                            default_sql = str(int(arg))
                        elif isinstance(arg, (int, float)):
                            default_sql = str(arg)
                        else:
                            default_sql = f"'{arg}'"

                if not column.nullable:
                    # SQLite requires DEFAULT for NOT NULL in ALTER TABLE
                    if default_sql is None:
                        type_upper = str(col_type).upper()
                        if any(t in type_upper for t in ("INT", "BOOL")):
                            default_sql = "0"
                        elif any(t in type_upper for t in ("FLOAT", "REAL")):
                            default_sql = "0.0"
                        else:
                            default_sql = "''"
                    stmt += f" NOT NULL DEFAULT {default_sql}"
                elif default_sql is not None:
                    stmt += f" DEFAULT {default_sql}"

                logger.info("migrate: %s", stmt)
                conn.execute(stmt)

        conn.commit()
    finally:
        conn.close()

    # Verify: re-read the schema and warn about any columns still missing.
    conn = sqlite3.connect(db_path)
    try:
        for table in story.Base.metadata.sorted_tables:
            cursor = conn.execute(f"PRAGMA table_info({table.name})")
            existing_cols = {row[1] for row in cursor.fetchall()}
            if not existing_cols:
                continue
            model_cols = {c.name for c in table.columns}
            missing = model_cols - existing_cols
            if missing:
                logger.error(
                    "Schema mismatch after migration — table %r is missing "
                    "columns: %s",
                    table.name,
                    ", ".join(sorted(missing)),
                )
    finally:
        conn.close()


_migrate_db()
story.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Voice In The Dark", version="0.1.0")

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
