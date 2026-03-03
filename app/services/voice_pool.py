"""Auto-assign ElevenLabs voices to script characters from a diverse preset pool.

Each voice in the pool is tagged with gender, age range, and archetype keywords.
The assigner parses character voice_profile descriptions from the script, scores
each pool entry, and picks the best match — with slight random perturbation to
voice settings so two characters sharing a voice ID still sound distinct.
"""

import random
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class VoiceEntry:
    voice_id: str
    name: str
    gender: str  # "male", "female"
    age: str  # "young", "adult", "middle", "elder"
    archetypes: list[str]  # keyword tags for matching
    model: str = "eleven_v3"  # default model, could be extended for more complex pools


# Well-known ElevenLabs premade voices available on all plans.
VOICE_POOL: list[VoiceEntry] = [
    # ── Male voices ──────────────────────────────────────────────
    VoiceEntry("7p1Ofvcwsv7UBPoFNcpI", "Julian", "male", "adult",
               ["British", "deep", "rich", "mature", "narrator"],
               model="eleven_multilingual_v2"),
    VoiceEntry("Gsndh0O5AnuI2Hj3YUlA", "Adam", "male", "adult",
               ["narrator", "deep", "authoritative", "steady", "English"],
               model="eleven_multilingual_v2"),
    VoiceEntry("ErXwobaYiN019PkySvjV", "Antoni", "male", "adult",
               ["warm", "conversational", "friendly", "everyman"]),
    VoiceEntry("VR6AewLTigWG4xSOukaG", "Arnold", "male", "adult",
               ["crisp", "strong", "gruff", "tough", "military"]),
    VoiceEntry("TxGEqnHWrfWFTfGW9XjX", "Josh", "male", "young",
               ["young", "deep", "confident", "protagonist"]),
    VoiceEntry("yoZ06aMxZJJ28mfd3POQ", "Sam", "male", "adult",
               ["raspy", "rough", "sinister", "gravelly", "threatening"]),
    VoiceEntry("2EiwWnXFnvU5JabPnv8n", "Clyde", "male", "elder",
               ["old", "veteran", "weathered", "grizzled", "wise"]),
    VoiceEntry("onwK4e9ZLuTAKqWV03F9", "Daniel", "male", "adult",
               ["british", "authoritative", "formal", "narrator", "refined"]),
    VoiceEntry("SOYHLrjzK2X1ezoPC6cr", "Harry", "male", "young",
               ["young", "anxious", "nervous", "scared", "uncertain"]),
    VoiceEntry("uDsPstFWFBUXjIBimV7s", "Santa (yes, really)", "male", "elderly",
               ["warm", "playful", "jolly", "keeps lists", "checks them twice"],
               model="eleven_multilingual_v2"),
    VoiceEntry("GBv7mTt0atIp3Br8iCZE", "Thomas", "male", "adult",
               ["calm", "steady", "matter-of-fact", "professional"]),
    VoiceEntry("ZQe5CZNOzWyzPSCn5a3c", "James", "male", "elder",
               ["old", "calm", "gentle", "grandfather", "wise", "ominous"]),
    VoiceEntry("TX3LPaxmHKxFdv7VOQHJ", "Liam", "male", "young",
               ["young", "energetic", "narrator", "articulate"]),
    VoiceEntry("D38z5RcWu1voky8WS1ja", "Fin", "male", "adult",
               ["irish", "storyteller", "folksy", "eerie"]),
    VoiceEntry("CYw3kZ02Hs0563khs1Fj", "Dave", "male", "adult",
               ["conversational", "british", "everyman", "relatable"]),

    # ── Female voices ────────────────────────────────────────────
    VoiceEntry("21m00Tcm4TlvDq8ikWAM", "Rachel", "female", "adult",
               ["calm", "narrator", "warm", "composed", "steady"]),
    VoiceEntry("EXAVITQu4vr4xnSDxMaL", "Bella", "female", "young",
               ["soft", "gentle", "quiet", "whispery", "innocent"]),
    VoiceEntry("AZnzlk1XvdvUeBnXmlld", "Domi", "female", "adult",
               ["strong", "confident", "assertive", "commanding"]),
    VoiceEntry("MF3mGyEYCl7XYWbV9V6O", "Elli", "female", "young",
               ["young", "cheerful", "bright", "girl", "innocent"]),
    VoiceEntry("jsCqWAovK2LkecY7zXl4", "Freya", "female", "young",
               ["young", "narrator", "expressive", "protagonist"]),
    VoiceEntry("XB0fDUnXU5powFXDhCwa", "Charlotte", "female", "adult",
               ["seductive", "smooth", "mysterious", "sinister", "alluring"]),
    VoiceEntry("oWAxZDx7w5VEj9dCyTzz", "Grace", "female", "adult",
               ["southern", "warm", "motherly", "folksy"]),
    VoiceEntry("ThT5KcBeYPX3keUQqHPh", "Dorothy", "female", "young",
               ["young", "pleasant", "sweet", "kind"]),
    VoiceEntry("z9fAnlkpzviPz146aGWa", "Glinda", "female", "elder",
               ["old", "witch", "eerie", "sinister", "raspy", "crone"]),
    VoiceEntry("pMsXgVXv3BLzUgSXRplE", "Serena", "female", "middle",
               ["calm", "middle-aged", "professional", "composed"]),
    VoiceEntry("piTKgcLEGmPE4e6mEKli", "Nicole", "female", "adult",
               ["whisper", "quiet", "airy", "ethereal", "ghostly"]),
    VoiceEntry("jBpfuIE2acCO8z3wKNLl", "Gigi", "female", "young",
               ["child", "childish", "young", "small", "little"]),
]

# Keywords that signal gender
_FEMALE_CUES = {"female", "woman", "girl", "she", "her", "mother", "wife",
                "daughter", "sister", "lady", "feminine", "aunt", "grandmother"}
_MALE_CUES = {"male", "man", "boy", "he", "him", "father", "husband",
              "son", "brother", "guy", "masculine", "uncle", "grandfather"}

# Keywords that signal age
_YOUNG_CUES = {"young", "teen", "teenager", "child", "kid", "boy", "girl",
               "college", "student", "adolescent", "little"}
_ELDER_CUES = {"old", "elder", "elderly", "aged", "ancient", "grandfather",
               "grandmother", "grizzled", "weathered", "veteran", "senior"}


def _parse_profile(voice_profile: str) -> dict:
    """Extract gender, age, and keyword signals from a voice_profile string."""
    words = set(voice_profile.lower().replace(",", " ").replace(".", " ").split())

    gender = None
    if words & _FEMALE_CUES:
        gender = "female"
    elif words & _MALE_CUES:
        gender = "male"

    age = None
    if words & _YOUNG_CUES:
        age = "young"
    elif words & _ELDER_CUES:
        age = "elder"

    return {"gender": gender, "age": age, "words": words}


def _score_voice(entry: VoiceEntry, profile: dict) -> float:
    """Score how well a VoiceEntry matches a parsed character profile."""
    score = 0.0

    # Gender match is most important
    if profile["gender"]:
        if entry.gender == profile["gender"]:
            score += 10.0
        else:
            score -= 20.0  # strong penalty for gender mismatch

    # Age match
    if profile["age"]:
        if profile["age"] == "young" and entry.age == "young":
            score += 5.0
        elif profile["age"] == "elder" and entry.age == "elder":
            score += 5.0
        elif profile["age"] == entry.age:
            score += 3.0

    # Archetype keyword overlap
    keyword_overlap = profile["words"] & set(entry.archetypes)
    score += len(keyword_overlap) * 2.0

    # Small random jitter so ties are broken differently each time
    score += random.uniform(0, 1.5)

    return score


def auto_assign_voices(
    characters: dict[str, "CharacterProfile"],
) -> dict[str, str]:
    """Assign a voice_id from the pool to each character in the script.

    Args:
        characters: The script's characters dict (key -> CharacterProfile).

    Returns:
        voice_map: dict mapping character key -> ElevenLabs voice ID.
    """
    voice_map: dict[str, str] = {}
    used_ids: set[str] = set()

    # Sort characters so "narrator" is assigned first (most important)
    char_keys = sorted(characters.keys(), key=lambda k: (k != "narrator", k))

    for char_key in char_keys:
        char = characters[char_key]

        # If the character already has a voice_id manually assigned, use it
        if char.voice_id:
            voice_map[char_key] = char.voice_id
            used_ids.add(char.voice_id)
            logger.info(
                f"Voice pre-assigned: {char_key} -> {char.voice_id[:8]}... "
                f"[profile: {char.voice_profile[:50]}]"
            )
            continue

        profile = _parse_profile(char.voice_profile)

        # Score all voices, preferring unused ones
        candidates = []
        for entry in VOICE_POOL:
            score = _score_voice(entry, profile)
            # Penalize reuse but don't forbid it (pool might be smaller than cast)
            if entry.voice_id in used_ids:
                score -= 8.0
            candidates.append((score, entry))

        candidates.sort(key=lambda x: x[0], reverse=True)
        best = candidates[0][1]

        voice_map[char_key] = best.voice_id
        used_ids.add(best.voice_id)
        logger.info(
            f"Voice assigned: {char_key} -> {best.name} ({best.voice_id[:8]}...) "
            f"[profile: {char.voice_profile[:50]}]"
        )

    return voice_map
