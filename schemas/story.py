"""Pydantic schemas for story-related API requests and responses.

Framework-agnostic — works with both FastAPI and Django Ninja.
"""

from datetime import datetime
from typing import Optional

from ninja import Schema
from pydantic import Field, StringConstraints
from typing import Annotated


# ── Auth schemas ─────────────────────────────────────────────────


class RegisterRequest(Schema):
    username: str
    password: str


class LoginRequest(Schema):
    username: str
    password: str


class UserResponse(Schema):
    id: int
    username: str
    is_admin: bool = False

    @staticmethod
    def from_user(user) -> "UserResponse":
        return UserResponse(
            id=user.id,
            username=user.username,
            is_admin=user.is_staff,
        )


class TokenResponse(Schema):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ── Story schemas ────────────────────────────────────────────────


class StorySubmitRequest(Schema):
    reddit_url: str


class ManualStorySubmitRequest(Schema):
    title: Optional[str] = None
    author: Optional[str] = None
    text_content: Optional[str] = None
    reddit_url: Optional[str] = None


class StoryResponse(Schema):
    id: int
    title: str
    author: Optional[str] = None
    reddit_url: Optional[str] = None
    narration_text: Optional[str] = None
    content_hash: str
    audio_file_path: Optional[str] = None
    part_count: int = 1
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class StoryListResponse(Schema):
    id: int
    title: str
    author: Optional[str] = None
    reddit_url: Optional[str] = None
    has_audio: bool
    has_script: bool
    part_count: int = 1
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Audio schemas ────────────────────────────────────────────────


class GenerateAudioRequest(Schema):
    story_id: int
    voice_id: str
    force_regenerate: bool = False


class GenerateScriptRequest(Schema):
    story_id: int
    force_regenerate: bool = False


class GenerateNarrationRequest(Schema):
    story_id: int
    voice_map: Optional[dict[str, str]] = None
    force_regenerate: bool = False
    bust_cache: bool = False


# ── Playback schemas ────────────────────────────────────────────


class PlaybackStateRequest(Schema):
    story_id: int
    position_seconds: float


class PlaybackStateResponse(Schema):
    story_id: int
    user_id: Optional[int] = None
    position_seconds: float
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Duplicate check ──────────────────────────────────────────────


class DuplicateCheckResponse(Schema):
    is_duplicate: bool
    existing_story_id: Optional[int] = None
    message: str


# ── Folder schemas ───────────────────────────────────────────────


class FolderCreateRequest(Schema):
    name: Annotated[str, StringConstraints(min_length=1, max_length=60, strip_whitespace=True)]


class FolderResponse(Schema):
    id: int
    name: str
    story_count: int = 0
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class FolderAddStoryRequest(Schema):
    story_id: int = Field(gt=0)
