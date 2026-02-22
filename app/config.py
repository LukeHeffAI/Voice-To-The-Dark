import os
from dotenv import load_dotenv

load_dotenv()  # load from .env

class Settings:
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
    REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
    REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

settings = Settings()