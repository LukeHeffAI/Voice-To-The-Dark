from sqlalchemy import Column, Integer, String, Text, Boolean, Float, DateTime, UniqueConstraint
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
    author = Column(String, nullable=True)
    audio_file_path = Column(String, nullable=True)
    part_count = Column(Integer, default=1)
    series_json = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PlaybackState(Base):
    __tablename__ = 'playback_states'
    __table_args__ = (
        UniqueConstraint('user_id', 'story_id', name='uq_user_story_playback'),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    story_id = Column(Integer, nullable=False, index=True)
    position_seconds = Column(Float, default=0.0)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class StoryView(Base):
    """Tracks when a user views a story, powering the 'Recently Viewed' home page."""
    __tablename__ = 'story_views'
    __table_args__ = (
        UniqueConstraint('user_id', 'story_id', name='uq_user_story_view'),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    story_id = Column(Integer, nullable=False, index=True)
    viewed_at = Column(DateTime, server_default=func.now())
    hidden = Column(Boolean, default=False)


class StoryFolder(Base):
    """User-created folders for organising stories."""
    __tablename__ = 'story_folders'
    __table_args__ = (
        UniqueConstraint('user_id', 'name', name='uq_user_folder_name'),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class StoryFolderMembership(Base):
    """Junction table linking stories to folders."""
    __tablename__ = 'story_folder_memberships'
    __table_args__ = (
        UniqueConstraint('folder_id', 'story_id', name='uq_folder_story'),
    )

    id = Column(Integer, primary_key=True, index=True)
    folder_id = Column(Integer, nullable=False, index=True)
    story_id = Column(Integer, nullable=False, index=True)
    added_at = Column(DateTime, server_default=func.now())


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    is_admin = Column(Boolean, default=False)
