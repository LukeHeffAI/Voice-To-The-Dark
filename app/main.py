from fastapi import FastAPI
from .database import engine
from .models import story  # load all models

story.Base.metadata.create_all(bind=engine)

app = FastAPI()

# Include routers
# ...
