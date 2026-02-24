from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import datetime


class StorySubmitRequest(BaseModel):
    reddit_url: str


class ManualStorySubmitRequest(BaseModel):
    title: str
    text_content: str
    reddit_url: Optional[str] = None


class StoryResponse(BaseModel):
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


class StoryListResponse(BaseModel):
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


class GenerateScriptRequest(BaseModel):
    story_id: int
    force_regenerate: bool = False


class GenerateNarrationRequest(BaseModel):
    story_id: int
    voice_map: Optional[dict[str, str]] = None  # auto-assigned if omitted
    force_regenerate: bool = False


class PlaybackStateRequest(BaseModel):
    story_id: int
    position_seconds: float


class PlaybackStateResponse(BaseModel):
    story_id: int
    position_seconds: float
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DuplicateCheckResponse(BaseModel):
    is_duplicate: bool
    existing_story_id: Optional[int] = None
    message: str
