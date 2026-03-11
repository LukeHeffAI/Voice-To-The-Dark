"""Comprehensive tests for all Pydantic schemas in app.schemas."""

import pytest
from datetime import datetime
from pydantic import ValidationError

from app.schemas.story import (
    StorySubmitRequest,
    ManualStorySubmitRequest,
    StoryResponse,
    StoryListResponse,
    GenerateScriptRequest,
    GenerateNarrationRequest,
    PlaybackStateRequest,
    PlaybackStateResponse,
    DuplicateCheckResponse,
    FolderCreateRequest,
    FolderResponse,
    FolderAddStoryRequest,
)
from app.schemas.narration import (
    SegmentType,
    CharacterProfile,
    ScriptSegment,
    NarrationScript,
)


# ---------------------------------------------------------------------------
# StorySubmitRequest
# ---------------------------------------------------------------------------

class TestStorySubmitRequest:

    def test_valid_url(self):
        req = StorySubmitRequest(reddit_url="https://reddit.com/r/nosleep/abc")
        assert req.reddit_url == "https://reddit.com/r/nosleep/abc"

    def test_missing_reddit_url_raises(self):
        with pytest.raises(ValidationError):
            StorySubmitRequest()

    def test_empty_string_allowed(self):
        """reddit_url is typed as plain str, so empty string passes validation."""
        req = StorySubmitRequest(reddit_url="")
        assert req.reddit_url == ""

    def test_model_dump(self):
        req = StorySubmitRequest(reddit_url="https://example.com")
        d = req.model_dump()
        assert d == {"reddit_url": "https://example.com"}

    def test_round_trip(self):
        data = {"reddit_url": "https://reddit.com/r/x"}
        obj = StorySubmitRequest.model_validate(data)
        assert obj.model_dump() == data


# ---------------------------------------------------------------------------
# ManualStorySubmitRequest
# ---------------------------------------------------------------------------

class TestManualStorySubmitRequest:

    def test_all_defaults(self):
        req = ManualStorySubmitRequest()
        assert req.title is None
        assert req.author is None
        assert req.text_content is None
        assert req.reddit_url is None

    def test_all_fields_set(self):
        req = ManualStorySubmitRequest(
            title="My Title",
            author="Author",
            text_content="Once upon a time...",
            reddit_url="https://reddit.com/r/nosleep/123",
        )
        assert req.title == "My Title"
        assert req.author == "Author"
        assert req.text_content == "Once upon a time..."
        assert req.reddit_url == "https://reddit.com/r/nosleep/123"

    def test_partial_fields(self):
        req = ManualStorySubmitRequest(title="Title Only")
        assert req.title == "Title Only"
        assert req.author is None

    def test_model_dump_all_none(self):
        d = ManualStorySubmitRequest().model_dump()
        assert d == {
            "title": None,
            "author": None,
            "text_content": None,
            "reddit_url": None,
        }

    def test_round_trip(self):
        data = {"title": "T", "author": "A", "text_content": "C", "reddit_url": None}
        obj = ManualStorySubmitRequest.model_validate(data)
        assert obj.model_dump() == data


# ---------------------------------------------------------------------------
# StoryResponse
# ---------------------------------------------------------------------------

class TestStoryResponse:

    @pytest.fixture()
    def minimal_data(self):
        return {"id": 1, "title": "A Story", "content_hash": "abc123"}

    def test_minimal_construction(self, minimal_data):
        resp = StoryResponse(**minimal_data)
        assert resp.id == 1
        assert resp.title == "A Story"
        assert resp.content_hash == "abc123"
        assert resp.author is None
        assert resp.reddit_url is None
        assert resp.narration_text is None
        assert resp.audio_file_path is None
        assert resp.part_count == 1
        assert resp.created_at is None

    def test_full_construction(self):
        now = datetime(2025, 1, 15, 12, 0, 0)
        resp = StoryResponse(
            id=42,
            title="Horror Story",
            author="spooky_writer",
            reddit_url="https://reddit.com/r/nosleep/42",
            narration_text="It was a dark and stormy night.",
            content_hash="deadbeef",
            audio_file_path="/audio/42.mp3",
            part_count=3,
            created_at=now,
        )
        assert resp.id == 42
        assert resp.part_count == 3
        assert resp.created_at == now

    def test_missing_required_fields(self):
        with pytest.raises(ValidationError):
            StoryResponse(id=1, title="T")  # missing content_hash

        with pytest.raises(ValidationError):
            StoryResponse(id=1, content_hash="h")  # missing title

        with pytest.raises(ValidationError):
            StoryResponse(title="T", content_hash="h")  # missing id

    def test_from_attributes_config(self):
        assert StoryResponse.model_config.get("from_attributes") is True

    def test_from_attributes_orm_style(self):
        """Verify the schema can be constructed from an object with attributes."""

        class FakeORM:
            id = 10
            title = "ORM Title"
            author = None
            reddit_url = None
            narration_text = None
            content_hash = "ormhash"
            audio_file_path = None
            part_count = 1
            created_at = None

        resp = StoryResponse.model_validate(FakeORM(), from_attributes=True)
        assert resp.id == 10
        assert resp.title == "ORM Title"

    def test_model_dump_keys(self, minimal_data):
        resp = StoryResponse(**minimal_data)
        d = resp.model_dump()
        expected_keys = {
            "id", "title", "author", "reddit_url", "narration_text",
            "content_hash", "audio_file_path", "part_count", "created_at",
        }
        assert set(d.keys()) == expected_keys

    def test_round_trip(self, minimal_data):
        obj = StoryResponse.model_validate(minimal_data)
        assert StoryResponse.model_validate(obj.model_dump()).model_dump() == obj.model_dump()


# ---------------------------------------------------------------------------
# StoryListResponse
# ---------------------------------------------------------------------------

class TestStoryListResponse:

    @pytest.fixture()
    def base_data(self):
        return {
            "id": 5,
            "title": "List Story",
            "has_audio": True,
            "has_script": False,
        }

    def test_valid_construction(self, base_data):
        resp = StoryListResponse(**base_data)
        assert resp.id == 5
        assert resp.title == "List Story"
        assert resp.has_audio is True
        assert resp.has_script is False
        assert resp.author is None
        assert resp.reddit_url is None
        assert resp.part_count == 1
        assert resp.created_at is None

    def test_has_audio_true(self, base_data):
        resp = StoryListResponse(**base_data)
        assert resp.has_audio is True

    def test_has_script_false(self, base_data):
        resp = StoryListResponse(**base_data)
        assert resp.has_script is False

    def test_has_audio_and_script_both_false(self):
        resp = StoryListResponse(id=1, title="T", has_audio=False, has_script=False)
        assert resp.has_audio is False
        assert resp.has_script is False

    def test_has_audio_and_script_both_true(self):
        resp = StoryListResponse(id=1, title="T", has_audio=True, has_script=True)
        assert resp.has_audio is True
        assert resp.has_script is True

    def test_missing_has_audio_raises(self):
        with pytest.raises(ValidationError):
            StoryListResponse(id=1, title="T", has_script=False)

    def test_missing_has_script_raises(self):
        with pytest.raises(ValidationError):
            StoryListResponse(id=1, title="T", has_audio=True)

    def test_from_attributes_config(self):
        assert StoryListResponse.model_config.get("from_attributes") is True

    def test_from_attributes_orm_style(self):
        class FakeORM:
            id = 7
            title = "ORM List"
            author = "me"
            reddit_url = None
            has_audio = False
            has_script = True
            part_count = 2
            created_at = None

        resp = StoryListResponse.model_validate(FakeORM(), from_attributes=True)
        assert resp.id == 7
        assert resp.has_script is True
        assert resp.part_count == 2

    def test_model_dump(self, base_data):
        resp = StoryListResponse(**base_data)
        d = resp.model_dump()
        assert d["has_audio"] is True
        assert d["has_script"] is False

    def test_round_trip(self, base_data):
        obj = StoryListResponse.model_validate(base_data)
        assert StoryListResponse.model_validate(obj.model_dump()).model_dump() == obj.model_dump()

    def test_with_created_at(self):
        now = datetime(2025, 6, 1, 8, 30, 0)
        resp = StoryListResponse(
            id=1, title="T", has_audio=False, has_script=False, created_at=now,
        )
        assert resp.created_at == now


# ---------------------------------------------------------------------------
# GenerateScriptRequest
# ---------------------------------------------------------------------------

class TestGenerateScriptRequest:

    def test_defaults(self):
        req = GenerateScriptRequest(story_id=1)
        assert req.story_id == 1
        assert req.force_regenerate is False

    def test_force_regenerate_true(self):
        req = GenerateScriptRequest(story_id=5, force_regenerate=True)
        assert req.force_regenerate is True

    def test_missing_story_id(self):
        with pytest.raises(ValidationError):
            GenerateScriptRequest()

    def test_round_trip(self):
        data = {"story_id": 10, "force_regenerate": True}
        obj = GenerateScriptRequest.model_validate(data)
        assert obj.model_dump() == data


# ---------------------------------------------------------------------------
# GenerateNarrationRequest
# ---------------------------------------------------------------------------

class TestGenerateNarrationRequest:

    def test_defaults(self):
        req = GenerateNarrationRequest(story_id=1)
        assert req.story_id == 1
        assert req.voice_map is None
        assert req.force_regenerate is False
        assert req.bust_cache is False

    def test_with_voice_map(self):
        vm = {"narrator": "voice_abc", "villain": "voice_xyz"}
        req = GenerateNarrationRequest(story_id=2, voice_map=vm)
        assert req.voice_map == vm

    def test_missing_story_id(self):
        with pytest.raises(ValidationError):
            GenerateNarrationRequest()

    def test_round_trip(self):
        data = {"story_id": 3, "voice_map": {"a": "b"}, "force_regenerate": True, "bust_cache": False}
        obj = GenerateNarrationRequest.model_validate(data)
        assert obj.model_dump() == data


# ---------------------------------------------------------------------------
# PlaybackStateRequest
# ---------------------------------------------------------------------------

class TestPlaybackStateRequest:

    def test_valid(self):
        req = PlaybackStateRequest(story_id=10, position_seconds=42.5)
        assert req.story_id == 10
        assert req.position_seconds == 42.5

    def test_missing_story_id(self):
        with pytest.raises(ValidationError):
            PlaybackStateRequest(position_seconds=1.0)

    def test_missing_position_seconds(self):
        with pytest.raises(ValidationError):
            PlaybackStateRequest(story_id=1)

    def test_zero_position(self):
        req = PlaybackStateRequest(story_id=1, position_seconds=0.0)
        assert req.position_seconds == 0.0

    def test_negative_position(self):
        """No constraint prevents negative values, so this should succeed."""
        req = PlaybackStateRequest(story_id=1, position_seconds=-1.0)
        assert req.position_seconds == -1.0

    def test_large_position(self):
        req = PlaybackStateRequest(story_id=1, position_seconds=99999.99)
        assert req.position_seconds == 99999.99

    def test_model_dump(self):
        d = PlaybackStateRequest(story_id=3, position_seconds=7.7).model_dump()
        assert d == {"story_id": 3, "position_seconds": 7.7}

    def test_round_trip(self):
        data = {"story_id": 5, "position_seconds": 120.0}
        obj = PlaybackStateRequest.model_validate(data)
        assert obj.model_dump() == data


# ---------------------------------------------------------------------------
# PlaybackStateResponse
# ---------------------------------------------------------------------------

class TestPlaybackStateResponse:

    def test_minimal(self):
        resp = PlaybackStateResponse(story_id=1, position_seconds=0.0)
        assert resp.story_id == 1
        assert resp.position_seconds == 0.0
        assert resp.user_id is None
        assert resp.updated_at is None

    def test_full(self):
        now = datetime(2025, 3, 10, 9, 0, 0)
        resp = PlaybackStateResponse(
            story_id=2, user_id=100, position_seconds=55.5, updated_at=now,
        )
        assert resp.user_id == 100
        assert resp.updated_at == now

    def test_from_attributes_config(self):
        assert PlaybackStateResponse.model_config.get("from_attributes") is True

    def test_from_attributes_orm_style(self):
        class FakeORM:
            story_id = 8
            user_id = 3
            position_seconds = 99.9
            updated_at = datetime(2025, 1, 1)

        resp = PlaybackStateResponse.model_validate(FakeORM(), from_attributes=True)
        assert resp.story_id == 8
        assert resp.user_id == 3

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            PlaybackStateResponse(story_id=1)  # missing position_seconds
        with pytest.raises(ValidationError):
            PlaybackStateResponse(position_seconds=1.0)  # missing story_id

    def test_model_dump(self):
        resp = PlaybackStateResponse(story_id=1, position_seconds=0.0)
        d = resp.model_dump()
        expected_keys = {"story_id", "user_id", "position_seconds", "updated_at"}
        assert set(d.keys()) == expected_keys

    def test_round_trip(self):
        data = {"story_id": 1, "user_id": None, "position_seconds": 10.0, "updated_at": None}
        obj = PlaybackStateResponse.model_validate(data)
        assert obj.model_dump() == data


# ---------------------------------------------------------------------------
# DuplicateCheckResponse
# ---------------------------------------------------------------------------

class TestDuplicateCheckResponse:

    def test_not_duplicate(self):
        resp = DuplicateCheckResponse(
            is_duplicate=False, message="No duplicate found.",
        )
        assert resp.is_duplicate is False
        assert resp.existing_story_id is None
        assert resp.message == "No duplicate found."

    def test_is_duplicate(self):
        resp = DuplicateCheckResponse(
            is_duplicate=True, existing_story_id=42, message="Duplicate of story 42.",
        )
        assert resp.is_duplicate is True
        assert resp.existing_story_id == 42

    def test_missing_is_duplicate(self):
        with pytest.raises(ValidationError):
            DuplicateCheckResponse(message="oops")

    def test_missing_message(self):
        with pytest.raises(ValidationError):
            DuplicateCheckResponse(is_duplicate=False)

    def test_existing_story_id_default_none(self):
        resp = DuplicateCheckResponse(is_duplicate=False, message="ok")
        assert resp.existing_story_id is None

    def test_model_dump(self):
        resp = DuplicateCheckResponse(
            is_duplicate=True, existing_story_id=7, message="dup",
        )
        d = resp.model_dump()
        assert d == {"is_duplicate": True, "existing_story_id": 7, "message": "dup"}

    def test_round_trip(self):
        data = {"is_duplicate": True, "existing_story_id": 1, "message": "found"}
        obj = DuplicateCheckResponse.model_validate(data)
        assert obj.model_dump() == data


# ---------------------------------------------------------------------------
# FolderCreateRequest
# ---------------------------------------------------------------------------

class TestFolderCreateRequest:

    def test_valid_name(self):
        req = FolderCreateRequest(name="My Folder")
        assert req.name == "My Folder"

    def test_strip_whitespace(self):
        req = FolderCreateRequest(name="  padded  ")
        assert req.name == "padded"

    def test_empty_string_after_strip_raises(self):
        """After stripping, empty string violates min_length=1."""
        with pytest.raises(ValidationError):
            FolderCreateRequest(name="   ")

    def test_empty_string_raises(self):
        with pytest.raises(ValidationError):
            FolderCreateRequest(name="")

    def test_exactly_one_char(self):
        req = FolderCreateRequest(name="A")
        assert req.name == "A"

    def test_max_length_60(self):
        name = "x" * 60
        req = FolderCreateRequest(name=name)
        assert req.name == name

    def test_exceeds_max_length_raises(self):
        with pytest.raises(ValidationError):
            FolderCreateRequest(name="x" * 61)

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            FolderCreateRequest()

    def test_model_dump(self):
        req = FolderCreateRequest(name="Test")
        assert req.model_dump() == {"name": "Test"}

    def test_round_trip(self):
        data = {"name": "Favorites"}
        obj = FolderCreateRequest.model_validate(data)
        assert obj.model_dump() == data

    def test_boundary_59_chars(self):
        name = "a" * 59
        req = FolderCreateRequest(name=name)
        assert len(req.name) == 59

    def test_unicode_name(self):
        req = FolderCreateRequest(name="Dossier Histoires")
        assert req.name == "Dossier Histoires"


# ---------------------------------------------------------------------------
# FolderResponse
# ---------------------------------------------------------------------------

class TestFolderResponse:

    def test_minimal(self):
        resp = FolderResponse(id=1, name="Default")
        assert resp.id == 1
        assert resp.name == "Default"
        assert resp.story_count == 0
        assert resp.created_at is None

    def test_full(self):
        now = datetime(2025, 7, 4, 12, 0, 0)
        resp = FolderResponse(id=5, name="Horror", story_count=13, created_at=now)
        assert resp.story_count == 13
        assert resp.created_at == now

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            FolderResponse(name="X")  # missing id
        with pytest.raises(ValidationError):
            FolderResponse(id=1)  # missing name

    def test_from_attributes_config(self):
        assert FolderResponse.model_config.get("from_attributes") is True

    def test_from_attributes_orm_style(self):
        class FakeORM:
            id = 9
            name = "ORM Folder"
            story_count = 5
            created_at = None

        resp = FolderResponse.model_validate(FakeORM(), from_attributes=True)
        assert resp.id == 9
        assert resp.name == "ORM Folder"
        assert resp.story_count == 5

    def test_model_dump(self):
        resp = FolderResponse(id=1, name="F")
        d = resp.model_dump()
        assert set(d.keys()) == {"id", "name", "story_count", "created_at"}
        assert d["story_count"] == 0

    def test_round_trip(self):
        data = {"id": 2, "name": "Sci-Fi", "story_count": 4, "created_at": None}
        obj = FolderResponse.model_validate(data)
        assert obj.model_dump() == data


# ---------------------------------------------------------------------------
# FolderAddStoryRequest
# ---------------------------------------------------------------------------

class TestFolderAddStoryRequest:

    def test_valid(self):
        req = FolderAddStoryRequest(story_id=1)
        assert req.story_id == 1

    def test_large_story_id(self):
        req = FolderAddStoryRequest(story_id=999999)
        assert req.story_id == 999999

    def test_zero_raises(self):
        """story_id must be > 0."""
        with pytest.raises(ValidationError):
            FolderAddStoryRequest(story_id=0)

    def test_negative_raises(self):
        with pytest.raises(ValidationError):
            FolderAddStoryRequest(story_id=-1)

    def test_missing_story_id_raises(self):
        with pytest.raises(ValidationError):
            FolderAddStoryRequest()

    def test_model_dump(self):
        assert FolderAddStoryRequest(story_id=5).model_dump() == {"story_id": 5}

    def test_round_trip(self):
        data = {"story_id": 10}
        obj = FolderAddStoryRequest.model_validate(data)
        assert obj.model_dump() == data


# ---------------------------------------------------------------------------
# SegmentType enum
# ---------------------------------------------------------------------------

class TestSegmentType:

    def test_all_values_exist(self):
        assert SegmentType.NARRATION.value == "narration"
        assert SegmentType.DIALOGUE.value == "dialogue"
        assert SegmentType.SFX.value == "sfx"
        assert SegmentType.AMBIENT.value == "ambient"
        assert SegmentType.PAUSE.value == "pause"

    def test_member_count(self):
        assert len(SegmentType) == 5

    def test_is_str_subclass(self):
        assert isinstance(SegmentType.NARRATION, str)

    def test_string_equality(self):
        assert SegmentType.SFX == "sfx"

    def test_lookup_by_value(self):
        assert SegmentType("narration") is SegmentType.NARRATION
        assert SegmentType("dialogue") is SegmentType.DIALOGUE
        assert SegmentType("sfx") is SegmentType.SFX
        assert SegmentType("ambient") is SegmentType.AMBIENT
        assert SegmentType("pause") is SegmentType.PAUSE

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            SegmentType("invalid")

    def test_iteration(self):
        values = {member.value for member in SegmentType}
        assert values == {"narration", "dialogue", "sfx", "ambient", "pause"}


# ---------------------------------------------------------------------------
# CharacterProfile
# ---------------------------------------------------------------------------

class TestCharacterProfile:

    def test_valid(self):
        cp = CharacterProfile(voice_profile="deep, steady, ominous")
        assert cp.voice_profile == "deep, steady, ominous"
        assert cp.voice_id is None

    def test_with_voice_id(self):
        cp = CharacterProfile(voice_profile="soft", voice_id="el_voice_123")
        assert cp.voice_id == "el_voice_123"

    def test_missing_voice_profile_raises(self):
        with pytest.raises(ValidationError):
            CharacterProfile()

    def test_empty_voice_profile(self):
        """Empty string is valid since there is no min_length constraint."""
        cp = CharacterProfile(voice_profile="")
        assert cp.voice_profile == ""

    def test_model_dump(self):
        cp = CharacterProfile(voice_profile="gruff", voice_id="v1")
        d = cp.model_dump()
        assert d == {"voice_profile": "gruff", "voice_id": "v1"}

    def test_model_dump_default(self):
        cp = CharacterProfile(voice_profile="calm")
        d = cp.model_dump()
        assert d == {"voice_profile": "calm", "voice_id": None}

    def test_round_trip(self):
        data = {"voice_profile": "breathy, low", "voice_id": None}
        obj = CharacterProfile.model_validate(data)
        assert obj.model_dump() == data

    def test_round_trip_with_voice_id(self):
        data = {"voice_profile": "energetic", "voice_id": "xyz"}
        obj = CharacterProfile.model_validate(data)
        assert obj.model_dump() == data


# ---------------------------------------------------------------------------
# ScriptSegment
# ---------------------------------------------------------------------------

class TestScriptSegment:

    def test_narration_segment(self):
        seg = ScriptSegment(
            type=SegmentType.NARRATION,
            character="narrator",
            text="The night was dark.",
            tone="foreboding",
        )
        assert seg.type == SegmentType.NARRATION
        assert seg.character == "narrator"
        assert seg.text == "The night was dark."
        assert seg.tone == "foreboding"
        assert seg.description is None
        assert seg.duration_ms is None
        assert seg.loop is False

    def test_dialogue_segment(self):
        seg = ScriptSegment(
            type=SegmentType.DIALOGUE,
            character="villain",
            text="You cannot escape.",
            tone="menacing",
        )
        assert seg.type == SegmentType.DIALOGUE
        assert seg.character == "villain"

    def test_sfx_segment(self):
        seg = ScriptSegment(
            type=SegmentType.SFX,
            description="door creaking slowly",
        )
        assert seg.type == SegmentType.SFX
        assert seg.description == "door creaking slowly"
        assert seg.character is None
        assert seg.text is None

    def test_ambient_segment(self):
        seg = ScriptSegment(
            type=SegmentType.AMBIENT,
            description="rain on roof",
            loop=True,
        )
        assert seg.type == SegmentType.AMBIENT
        assert seg.loop is True

    def test_ambient_loop_default_false(self):
        seg = ScriptSegment(type=SegmentType.AMBIENT, description="wind")
        assert seg.loop is False

    def test_pause_segment(self):
        seg = ScriptSegment(type=SegmentType.PAUSE, duration_ms=1500)
        assert seg.type == SegmentType.PAUSE
        assert seg.duration_ms == 1500

    def test_missing_type_raises(self):
        with pytest.raises(ValidationError):
            ScriptSegment(text="no type")

    def test_invalid_type_raises(self):
        with pytest.raises(ValidationError):
            ScriptSegment(type="not_a_type")

    def test_all_optional_fields_default_none(self):
        seg = ScriptSegment(type=SegmentType.PAUSE)
        assert seg.character is None
        assert seg.text is None
        assert seg.tone is None
        assert seg.description is None
        assert seg.duration_ms is None
        assert seg.loop is False

    def test_type_from_string_value(self):
        seg = ScriptSegment(type="narration", text="hello")
        assert seg.type == SegmentType.NARRATION

    def test_model_dump_narration(self):
        seg = ScriptSegment(
            type=SegmentType.NARRATION, character="nar", text="Hi",
        )
        d = seg.model_dump()
        assert d["type"] == SegmentType.NARRATION
        assert d["character"] == "nar"
        assert d["text"] == "Hi"
        assert d["loop"] is False

    def test_model_dump_pause(self):
        seg = ScriptSegment(type=SegmentType.PAUSE, duration_ms=500)
        d = seg.model_dump()
        assert d["duration_ms"] == 500

    def test_round_trip(self):
        data = {
            "type": "dialogue",
            "character": "hero",
            "text": "I will stop you!",
            "tone": "determined",
            "description": None,
            "duration_ms": None,
            "loop": False,
        }
        obj = ScriptSegment.model_validate(data)
        dumped = obj.model_dump()
        assert dumped["character"] == "hero"
        assert dumped["type"] == SegmentType.DIALOGUE

    def test_zero_duration_ms(self):
        seg = ScriptSegment(type=SegmentType.PAUSE, duration_ms=0)
        assert seg.duration_ms == 0

    def test_negative_duration_ms_allowed(self):
        """No explicit constraint on duration_ms, so negatives pass."""
        seg = ScriptSegment(type=SegmentType.PAUSE, duration_ms=-100)
        assert seg.duration_ms == -100


# ---------------------------------------------------------------------------
# NarrationScript
# ---------------------------------------------------------------------------

class TestNarrationScript:

    @pytest.fixture()
    def sample_characters(self):
        return {
            "narrator": CharacterProfile(voice_profile="deep, calm"),
            "monster": CharacterProfile(voice_profile="guttural, raspy"),
        }

    @pytest.fixture()
    def sample_segments(self):
        return [
            ScriptSegment(type=SegmentType.NARRATION, character="narrator", text="It began."),
            ScriptSegment(type=SegmentType.DIALOGUE, character="monster", text="Raaargh!"),
            ScriptSegment(type=SegmentType.SFX, description="crash"),
            ScriptSegment(type=SegmentType.AMBIENT, description="wind howling", loop=True),
            ScriptSegment(type=SegmentType.PAUSE, duration_ms=2000),
        ]

    @pytest.fixture()
    def sample_script(self, sample_characters, sample_segments):
        return NarrationScript(
            title="Test Script",
            characters=sample_characters,
            segments=sample_segments,
        )

    def test_valid_construction(self, sample_script):
        assert sample_script.title == "Test Script"
        assert len(sample_script.characters) == 2
        assert len(sample_script.segments) == 5

    def test_missing_title_raises(self):
        with pytest.raises(ValidationError):
            NarrationScript(characters={}, segments=[])

    def test_missing_characters_raises(self):
        with pytest.raises(ValidationError):
            NarrationScript(title="T", segments=[])

    def test_missing_segments_raises(self):
        with pytest.raises(ValidationError):
            NarrationScript(title="T", characters={})

    def test_empty_characters_and_segments(self):
        script = NarrationScript(title="Empty", characters={}, segments=[])
        assert script.characters == {}
        assert script.segments == []

    def test_voice_segments(self, sample_script):
        voice = sample_script.voice_segments()
        assert len(voice) == 2
        types = {s.type for s in voice}
        assert types == {SegmentType.NARRATION, SegmentType.DIALOGUE}

    def test_sfx_segments(self, sample_script):
        sfx = sample_script.sfx_segments()
        assert len(sfx) == 1
        assert sfx[0].description == "crash"

    def test_ambient_segments(self, sample_script):
        ambient = sample_script.ambient_segments()
        assert len(ambient) == 1
        assert ambient[0].description == "wind howling"
        assert ambient[0].loop is True

    def test_character_names(self, sample_script):
        names = sample_script.character_names()
        assert set(names) == {"narrator", "monster"}

    def test_character_names_empty(self):
        script = NarrationScript(title="T", characters={}, segments=[])
        assert script.character_names() == []

    def test_voice_segments_empty_when_no_voice_types(self):
        script = NarrationScript(
            title="T",
            characters={},
            segments=[
                ScriptSegment(type=SegmentType.SFX, description="bang"),
                ScriptSegment(type=SegmentType.PAUSE, duration_ms=100),
            ],
        )
        assert script.voice_segments() == []

    def test_sfx_segments_empty_when_no_sfx(self):
        script = NarrationScript(
            title="T",
            characters={"n": CharacterProfile(voice_profile="neutral")},
            segments=[
                ScriptSegment(type=SegmentType.NARRATION, character="n", text="Hi"),
            ],
        )
        assert script.sfx_segments() == []

    def test_ambient_segments_empty_when_no_ambient(self):
        script = NarrationScript(
            title="T",
            characters={},
            segments=[
                ScriptSegment(type=SegmentType.PAUSE, duration_ms=500),
            ],
        )
        assert script.ambient_segments() == []

    def test_model_dump(self, sample_script):
        d = sample_script.model_dump()
        assert d["title"] == "Test Script"
        assert "narrator" in d["characters"]
        assert d["characters"]["narrator"]["voice_profile"] == "deep, calm"
        assert len(d["segments"]) == 5

    def test_model_dump_segment_types(self, sample_script):
        d = sample_script.model_dump()
        seg_types = [seg["type"] for seg in d["segments"]]
        assert seg_types == [
            SegmentType.NARRATION,
            SegmentType.DIALOGUE,
            SegmentType.SFX,
            SegmentType.AMBIENT,
            SegmentType.PAUSE,
        ]

    def test_full_round_trip(self, sample_script):
        """Serialize to dict and deserialize back; verify structural equality."""
        d = sample_script.model_dump()
        restored = NarrationScript.model_validate(d)
        assert restored.title == sample_script.title
        assert len(restored.characters) == len(sample_script.characters)
        assert len(restored.segments) == len(sample_script.segments)
        for orig, rest in zip(sample_script.segments, restored.segments):
            assert orig.type == rest.type
            assert orig.text == rest.text
            assert orig.character == rest.character
            assert orig.description == rest.description
            assert orig.duration_ms == rest.duration_ms
            assert orig.loop == rest.loop

    def test_round_trip_from_raw_dict(self):
        """Build a NarrationScript from a raw nested dict (e.g. from JSON)."""
        raw = {
            "title": "From Raw",
            "characters": {
                "hero": {"voice_profile": "bold", "voice_id": "v_hero"},
            },
            "segments": [
                {"type": "dialogue", "character": "hero", "text": "Onward!", "tone": "brave",
                 "description": None, "duration_ms": None, "loop": False},
                {"type": "pause", "character": None, "text": None, "tone": None,
                 "description": None, "duration_ms": 1000, "loop": False},
            ],
        }
        script = NarrationScript.model_validate(raw)
        assert script.title == "From Raw"
        assert script.characters["hero"].voice_id == "v_hero"
        assert len(script.segments) == 2
        assert script.segments[0].type == SegmentType.DIALOGUE
        assert script.segments[1].duration_ms == 1000

    def test_round_trip_dump_validate_idempotent(self, sample_script):
        """model_validate(model_dump()) twice should be stable."""
        d1 = sample_script.model_dump()
        s1 = NarrationScript.model_validate(d1)
        d2 = s1.model_dump()
        assert d1 == d2

    def test_invalid_segment_in_list_raises(self):
        with pytest.raises(ValidationError):
            NarrationScript(
                title="Bad",
                characters={},
                segments=[{"type": "bogus_type"}],
            )

    def test_invalid_character_profile_raises(self):
        with pytest.raises(ValidationError):
            NarrationScript(
                title="Bad",
                characters={"x": {"not_voice_profile": "oops"}},
                segments=[],
            )

    def test_many_segments(self):
        segments = [
            ScriptSegment(type=SegmentType.NARRATION, character="n", text=f"Line {i}")
            for i in range(100)
        ]
        script = NarrationScript(
            title="Long",
            characters={"n": CharacterProfile(voice_profile="neutral")},
            segments=segments,
        )
        assert len(script.segments) == 100
        assert len(script.voice_segments()) == 100
        assert len(script.sfx_segments()) == 0

    def test_model_dump_json_round_trip(self, sample_script):
        """Verify JSON serialization round-trip works."""
        json_str = sample_script.model_dump_json()
        restored = NarrationScript.model_validate_json(json_str)
        assert restored.title == sample_script.title
        assert len(restored.segments) == len(sample_script.segments)
