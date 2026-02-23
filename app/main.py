import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from .database import engine
from .models import story  # load all models to register them with Base
from .routers import audio, stories, player, auth

story.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Voice To The Dark", version="0.1.0")

# Static files (icons for lock-screen artwork, etc.)
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# API routers
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(audio.router, prefix="/audio", tags=["audio"])
app.include_router(stories.router, prefix="/stories", tags=["stories"])

# Web UI (player pages served at the root)
app.include_router(player.router, tags=["player"])
