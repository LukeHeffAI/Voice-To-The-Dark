"""Tests for consecutive segment grouping in narration_generator."""

from schemas.narration import ScriptSegment, SegmentType
from services.narration_generator import _group_consecutive_segments


class TestGroupConsecutiveSegments:
    def test_empty_list(self):
        assert _group_consecutive_segments([]) == []

    def test_single_segment_unchanged(self):
        seg = ScriptSegment(
            type=SegmentType.NARRATION,
            character="narrator",
            text="The door opened slowly.",
            tone="foreboding",
        )
        result = _group_consecutive_segments([seg])
        assert len(result) == 1
        assert result[0].text == "The door opened slowly."
        assert result[0].character == "narrator"

    def test_consecutive_same_character_merged(self):
        segs = [
            ScriptSegment(type=SegmentType.NARRATION, character="narrator",
                          text="The house was silent.", tone="foreboding"),
            ScriptSegment(type=SegmentType.NARRATION, character="narrator",
                          text="Not a sound could be heard.", tone="foreboding"),
            ScriptSegment(type=SegmentType.NARRATION, character="narrator",
                          text="Until the screaming began.", tone="foreboding"),
        ]
        result = _group_consecutive_segments(segs)
        assert len(result) == 1
        assert result[0].text == "The house was silent. Not a sound could be heard. Until the screaming began."
        assert result[0].character == "narrator"
        assert result[0].tone == "foreboding"

    def test_different_characters_not_merged(self):
        segs = [
            ScriptSegment(type=SegmentType.NARRATION, character="narrator",
                          text="I looked at her.", tone="calm"),
            ScriptSegment(type=SegmentType.DIALOGUE, character="sarah",
                          text="What did you see?", tone="anxious"),
            ScriptSegment(type=SegmentType.NARRATION, character="narrator",
                          text="I couldn't answer.", tone="foreboding"),
        ]
        result = _group_consecutive_segments(segs)
        assert len(result) == 3
        assert result[0].text == "I looked at her."
        assert result[1].text == "What did you see?"
        assert result[2].text == "I couldn't answer."

    def test_non_voice_segments_break_groups(self):
        segs = [
            ScriptSegment(type=SegmentType.NARRATION, character="narrator",
                          text="First line.", tone="calm"),
            ScriptSegment(type=SegmentType.SFX, description="door creak"),
            ScriptSegment(type=SegmentType.NARRATION, character="narrator",
                          text="After the sound.", tone="calm"),
        ]
        result = _group_consecutive_segments(segs)
        assert len(result) == 3
        assert result[0].type == SegmentType.NARRATION
        assert result[0].text == "First line."
        assert result[1].type == SegmentType.SFX
        assert result[2].type == SegmentType.NARRATION
        assert result[2].text == "After the sound."

    def test_pause_breaks_group(self):
        segs = [
            ScriptSegment(type=SegmentType.NARRATION, character="narrator",
                          text="Before pause.", tone="calm"),
            ScriptSegment(type=SegmentType.PAUSE, duration_ms=1500),
            ScriptSegment(type=SegmentType.NARRATION, character="narrator",
                          text="After pause.", tone="calm"),
        ]
        result = _group_consecutive_segments(segs)
        assert len(result) == 3

    def test_different_tones_still_merged_with_shift(self):
        segs = [
            ScriptSegment(type=SegmentType.NARRATION, character="narrator",
                          text="Everything was fine.", tone="calm"),
            ScriptSegment(type=SegmentType.NARRATION, character="narrator",
                          text="Then the walls started bleeding.", tone="panicked"),
        ]
        result = _group_consecutive_segments(segs)
        assert len(result) == 1
        assert result[0].text == "Everything was fine. Then the walls started bleeding."
        assert "calm" in result[0].tone
        assert "panicked" in result[0].tone
        assert "shifting to" in result[0].tone

    def test_same_tone_merged_simply(self):
        segs = [
            ScriptSegment(type=SegmentType.DIALOGUE, character="sarah",
                          text="Don't go in there.", tone="whisper"),
            ScriptSegment(type=SegmentType.DIALOGUE, character="sarah",
                          text="Please, just don't.", tone="whisper"),
        ]
        result = _group_consecutive_segments(segs)
        assert len(result) == 1
        assert result[0].tone == "whisper"
        assert result[0].text == "Don't go in there. Please, just don't."

    def test_mixed_scenario(self):
        segs = [
            ScriptSegment(type=SegmentType.NARRATION, character="narrator",
                          text="Line one.", tone="calm"),
            ScriptSegment(type=SegmentType.NARRATION, character="narrator",
                          text="Line two.", tone="calm"),
            ScriptSegment(type=SegmentType.SFX, description="thunder"),
            ScriptSegment(type=SegmentType.DIALOGUE, character="sarah",
                          text="Did you hear that?", tone="scared"),
            ScriptSegment(type=SegmentType.NARRATION, character="narrator",
                          text="Line three.", tone="foreboding"),
            ScriptSegment(type=SegmentType.NARRATION, character="narrator",
                          text="Line four.", tone="foreboding"),
        ]
        result = _group_consecutive_segments(segs)
        assert len(result) == 4
        assert result[0].text == "Line one. Line two."
        assert result[0].type == SegmentType.NARRATION
        assert result[1].type == SegmentType.SFX
        assert result[2].text == "Did you hear that?"
        assert result[3].text == "Line three. Line four."

    def test_dialogue_and_narration_same_character_merged(self):
        segs = [
            ScriptSegment(type=SegmentType.NARRATION, character="narrator",
                          text="I whispered to myself.", tone="calm"),
            ScriptSegment(type=SegmentType.DIALOGUE, character="narrator",
                          text="What is happening?", tone="anxious"),
        ]
        result = _group_consecutive_segments(segs)
        assert len(result) == 1
        assert result[0].type == SegmentType.NARRATION
        assert result[0].text == "I whispered to myself. What is happening?"

    def test_preserves_non_voice_segment_order(self):
        segs = [
            ScriptSegment(type=SegmentType.AMBIENT, description="rain"),
            ScriptSegment(type=SegmentType.SFX, description="knock"),
            ScriptSegment(type=SegmentType.PAUSE, duration_ms=1000),
        ]
        result = _group_consecutive_segments(segs)
        assert len(result) == 3
        assert result[0].type == SegmentType.AMBIENT
        assert result[1].type == SegmentType.SFX
        assert result[2].type == SegmentType.PAUSE

    def test_none_tone_segments_merged(self):
        segs = [
            ScriptSegment(type=SegmentType.NARRATION, character="narrator",
                          text="First.", tone=None),
            ScriptSegment(type=SegmentType.NARRATION, character="narrator",
                          text="Second.", tone=None),
        ]
        result = _group_consecutive_segments(segs)
        assert len(result) == 1
        assert result[0].tone is None
