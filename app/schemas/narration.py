from pydantic import BaseModel
from typing import Optional
from enum import Enum


class SegmentType(str, Enum):
    NARRATION = "narration"
    DIALOGUE = "dialogue"
    SFX = "sfx"
    AMBIENT = "ambient"
    PAUSE = "pause"


class CharacterProfile(BaseModel):
    voice_profile: str  # e.g. "deep, steady, ominous"
    voice_id: Optional[str] = None  # ElevenLabs voice ID, assigned later


class ScriptSegment(BaseModel):
    type: SegmentType
    # For narration/dialogue segments
    character: Optional[str] = None  # key into characters dict
    text: Optional[str] = None
    tone: Optional[str] = None  # e.g. "foreboding", "panicked whisper"
    # For sfx/ambient segments
    description: Optional[str] = None  # e.g. "door creaking slowly"
    # For pause segments
    duration_ms: Optional[int] = None  # e.g. 1500
    # For ambient segments
    loop: bool = False


class NarrationScript(BaseModel):
    title: str
    characters: dict[str, CharacterProfile]
    segments: list[ScriptSegment]

    def voice_segments(self) -> list[ScriptSegment]:
        return [s for s in self.segments if s.type in (SegmentType.NARRATION, SegmentType.DIALOGUE)]

    def sfx_segments(self) -> list[ScriptSegment]:
        return [s for s in self.segments if s.type == SegmentType.SFX]

    def ambient_segments(self) -> list[ScriptSegment]:
        return [s for s in self.segments if s.type == SegmentType.AMBIENT]

    def character_names(self) -> list[str]:
        return list(self.characters.keys())
