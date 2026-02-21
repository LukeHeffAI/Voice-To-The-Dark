from fastapi import FastAPI
from .database import engine
from .models import story  # load all models to register them with Base
from .routers import audio, stories

story.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Voice To The Dark", version="0.1.0")

app.include_router(audio.router, prefix="/audio", tags=["audio"])
app.include_router(stories.router, prefix="/stories", tags=["stories"])
