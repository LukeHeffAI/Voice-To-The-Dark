from sqlalchemy import Column, Integer, String, Text, Boolean, Float, DateTime
from sqlalchemy.sql import func
from app.database import Base


class Story(Base):
    __tablename__ = 'stories'

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    reddit_url = Column(String, nullable=True, unique=True, index=True)
    text_content = Column(Text, nullable=False)
    narration_text = Column(Text, nullable=True)
    script_json = Column(Text, nullable=True)
    content_hash = Column(String(64), nullable=False, index=True)
    audio_file_path = Column(String, nullable=True)
    part_count = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PlaybackState(Base):
    __tablename__ = 'playback_states'

    id = Column(Integer, primary_key=True, index=True)
    story_id = Column(Integer, nullable=False, index=True)
    position_seconds = Column(Float, default=0.0)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    is_admin = Column(Boolean, default=False)
