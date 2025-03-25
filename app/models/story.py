from sqlalchemy import Column, Integer, String, Text, Boolean
from app.database import Base

class Story(Base):
    __tablename__ = 'stories'

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    reddit_url = Column(String, nullable=False)
    text_content = Column(Text, nullable=False)
    audio_file_path = Column(String, nullable=True)  # path to local or S3
    # Add columns for multi-part support if needed:
    # e.g., part_count, or a separate table referencing the story_id

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)  # or store an Argon2/Bcrypt-hashed password
    is_admin = Column(Boolean, default=False)