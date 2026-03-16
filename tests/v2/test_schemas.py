"""Tests for Pydantic narration schemas (ported from v1).

Story request/response schemas (StorySubmitRequest, etc.) will be ported
in Phase 4 when the API layer is built.
"""

import pytest
from pydantic import ValidationError

from schemas.narration import (
    SegmentType,
    CharacterProfile,
    ScriptSegment,
    NarrationScript,
)


# ---------------------------------------------------------------------------
# SegmentType
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
        json_str = sample_script.model_dump_json()
        restored = NarrationScript.model_validate_json(json_str)
        assert restored.title == sample_script.title
        assert len(restored.segments) == len(sample_script.segments)
