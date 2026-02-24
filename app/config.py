import os
from dotenv import load_dotenv

load_dotenv()  # load from .env

class Settings:
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change_me_to_a_random_secret")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRE_HOURS = 24 * 28  # 4 weeks

settings = Settings()