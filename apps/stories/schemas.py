from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from typing import Annotated


class StorySubmitRequest(BaseModel):
    reddit_url: str


class ManualStorySubmitRequest(BaseModel):
    title: str | None = None
    author: str | None = None
    text_content: str | None = None
    reddit_url: str | None = None


class StoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    author: str | None = None
    reddit_url: str | None = None
    narration_text: str | None = None
    content_hash: str
    audio_file_path: str | None = None
    part_count: int = 1
    created_at: datetime | None = None


class StoryListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    author: str | None = None
    reddit_url: str | None = None
    has_audio: bool
    has_script: bool
    part_count: int = 1
    created_at: datetime | None = None


class GenerateScriptRequest(BaseModel):
    story_id: int
    force_regenerate: bool = False


class GenerateNarrationRequest(BaseModel):
    story_id: int
    voice_map: dict[str, str] | None = None
    force_regenerate: bool = False
    bust_cache: bool = False


class GenerateAudioRequest(BaseModel):
    story_id: int
    voice_id: str
    force_regenerate: bool = False


class PlaybackStateRequest(BaseModel):
    story_id: int
    position_seconds: float


class PlaybackStateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    story_id: int
    user_id: int | None = None
    position_seconds: float
    updated_at: datetime | None = None


class DuplicateCheckResponse(BaseModel):
    is_duplicate: bool
    existing_story_id: int | None = None
    message: str


class FolderCreateRequest(BaseModel):
    name: Annotated[str, StringConstraints(min_length=1, max_length=60, strip_whitespace=True)]


class FolderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    story_count: int = 0
    created_at: datetime | None = None


class FolderAddStoryRequest(BaseModel):
    story_id: int = Field(gt=0)
