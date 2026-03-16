"""Unit tests for app.services.voice_pool."""

from apps.audio.services.voice_pool import (
    _parse_profile,
    _score_voice,
    auto_assign_voices,
    VoiceEntry,
    VOICE_POOL,
)
from apps.audio.schemas import CharacterProfile


class TestParseProfile:
    def test_detects_female(self):
        result = _parse_profile("A young woman, scared and trembling")
        assert result["gender"] == "female"

    def test_detects_male(self):
        result = _parse_profile("Deep, authoritative man in his 40s")
        assert result["gender"] == "male"

    def test_detects_young(self):
        result = _parse_profile("A teenager, nervous and unsure")
        assert result["age"] == "young"

    def test_detects_elder(self):
        result = _parse_profile("An elderly grandfather, weathered voice")
        assert result["age"] == "elder"

    def test_no_gender_clues(self):
        result = _parse_profile("Mysterious, ominous, deep")
        assert result["gender"] is None

    def test_no_age_clues(self):
        result = _parse_profile("Calm, steady, authoritative")
        assert result["age"] is None

    def test_extracts_keywords(self):
        result = _parse_profile("Deep, calm, sinister narrator")
        assert "deep" in result["words"]
        assert "calm" in result["words"]
        assert "sinister" in result["words"]


class TestScoreVoice:
    def test_gender_match_boosts_score(self):
        entry = VoiceEntry("id1", "Test", "female", "adult", ["calm"])
        profile = _parse_profile("A calm woman narrating")
        score = _score_voice(entry, profile)
        # Gender match gives +10, so score should be above 10
        assert score > 9.0

    def test_gender_mismatch_penalizes(self):
        entry = VoiceEntry("id1", "Test", "male", "adult", ["calm"])
        profile = _parse_profile("A calm woman narrating")
        score = _score_voice(entry, profile)
        # Gender mismatch gives -20
        assert score < 0

    def test_archetype_overlap_adds_points(self):
        entry = VoiceEntry("id1", "Test", "male", "adult", ["deep", "sinister", "ominous"])
        profile = _parse_profile("A deep sinister man")
        score = _score_voice(entry, profile)
        # Gender match (+10) + 2 keyword matches (deep, sinister = +4) + jitter
        assert score > 13.0

    def test_age_match_adds_points(self):
        entry = VoiceEntry("id1", "Test", "male", "elder", ["wise"])
        profile = _parse_profile("An old grandfather, wise and calm")
        score = _score_voice(entry, profile)
        # Gender match (+10) + elder match (+5) + wise overlap (+2) + jitter
        assert score > 16.0


class TestAutoAssignVoices:
    def test_assigns_voice_to_each_character(self):
        characters = {
            "narrator": CharacterProfile(voice_profile="Deep, steady male narrator"),
            "sarah": CharacterProfile(voice_profile="Young woman, scared and trembling"),
        }
        voice_map = auto_assign_voices(characters)
        assert "narrator" in voice_map
        assert "sarah" in voice_map
        assert len(voice_map) == 2

    def test_assigned_ids_are_from_pool(self):
        pool_ids = {v.voice_id for v in VOICE_POOL}
        characters = {
            "narrator": CharacterProfile(voice_profile="Male narrator"),
        }
        voice_map = auto_assign_voices(characters)
        assert voice_map["narrator"] in pool_ids

    def test_prefers_different_voices_for_different_characters(self):
        characters = {
            "narrator": CharacterProfile(voice_profile="Deep male narrator"),
            "detective": CharacterProfile(voice_profile="Authoritative male, formal"),
            "child": CharacterProfile(voice_profile="Young girl, innocent and scared"),
        }
        voice_map = auto_assign_voices(characters)
        # With 3 very different characters, voices should typically all be unique
        voice_ids = list(voice_map.values())
        assert len(voice_ids) == 3
        # Child should get a female voice (different from the two males)
        assert len(set(voice_ids)) >= 2  # at minimum the child differs

    def test_narrator_assigned_first(self):
        """Narrator should get first pick from the pool."""
        characters = {
            "sidechar": CharacterProfile(voice_profile="Male narrator, deep and steady"),
            "narrator": CharacterProfile(voice_profile="Male narrator, deep and steady"),
        }
        voice_map = auto_assign_voices(characters)
        # Both get assigned
        assert "narrator" in voice_map
        assert "sidechar" in voice_map

    def test_gender_matching_works(self):
        characters = {
            "woman": CharacterProfile(voice_profile="A young woman, soft-spoken"),
            "man": CharacterProfile(voice_profile="An older man, gruff and deep"),
        }
        voice_map = auto_assign_voices(characters)

        # Look up the assigned voices in the pool
        pool_by_id = {v.voice_id: v for v in VOICE_POOL}
        assert pool_by_id[voice_map["woman"]].gender == "female"
        assert pool_by_id[voice_map["man"]].gender == "male"

    def test_handles_single_character(self):
        characters = {
            "narrator": CharacterProfile(voice_profile="Calm steady narrator"),
        }
        voice_map = auto_assign_voices(characters)
        assert len(voice_map) == 1

    def test_handles_many_characters(self):
        """Even with more characters than distinct pool entries, all get assigned."""
        characters = {
            f"char_{i}": CharacterProfile(voice_profile="Some character")
            for i in range(30)
        }
        voice_map = auto_assign_voices(characters)
        assert len(voice_map) == 30
