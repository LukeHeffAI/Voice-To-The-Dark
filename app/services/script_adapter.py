import json
import logging
from anthropic import Anthropic
from app.config import settings
from app.schemas.narration import NarrationScript, CharacterProfile, ScriptSegment

logger = logging.getLogger(__name__)


class _TruncatedResponseError(Exception):
    """Raised when Claude's response is cut off by the max_tokens limit."""


# Claude's output token limit per request.  Sonnet supports much larger
# windows; 16 384 tokens gives long stories enough headroom while still
# keeping costs reasonable.  If a section *still* gets truncated the
# caller will automatically re-split and retry.
MAX_OUTPUT_TOKENS = 20000

#  TODO: review and refine the system prompt for better performance.
SYSTEM_PROMPT = """\
You are a horror audio drama director. Your job is to transform a written \
horror story into a structured narration script that will be performed by \
text-to-speech voices with sound effects and ambient audio.

You must produce a JSON object with this exact structure:

{
  "title": "<story title>",
  "characters": {
    "narrator": { "voice_profile": "<description of ideal voice>" },
    "<character_name>": { "voice_profile": "<description>" }
  },
  "segments": [
    { "type": "ambient", "description": "<atmospheric sound>", "loop": true },
    { "type": "narration", "character": "narrator", "text": "<line>", "tone": "<emotional direction>" },
    { "type": "dialogue", "character": "<name>", "text": "<line>", "tone": "<delivery direction>" },
    { "type": "sfx", "description": "<sound effect>" },
    { "type": "pause", "duration_ms": 1500 }
  ]
}

RULES FOR DRAMATIC HORROR NARRATION:

Voice & Pacing:
- The narrator voice should be measured, deliberate, and ominous. Not rushed.
- Dialogue should feel natural to the character — panicked characters speak in \
short bursts, calm ones in longer measured sentences.
- Use pauses (800-2000ms) to build tension. Place them before revelations, \
after jump scares, and at scene transitions.
- Vary sentence length within narration — short punchy lines for shock, \
longer flowing ones for atmosphere.

Sound Design:
- Open each scene with an ambient segment that establishes the setting \
(mark these with "loop": true).
- Insert SFX at moments of action or tension — but don't overdo it. \
2-4 SFX per scene is usually right.
- SFX descriptions should be specific and evocative: "heavy wooden door \
dragging across stone floor" not just "door sound".
- Ambient descriptions should layer sounds: "rain hammering on a tin roof, \
distant thunder, occasional drip from a leak".

Character Handling:
- The narrator is always the first-person voice of the story (the "I" perspective).
- Extract dialogue from the text and assign it to named characters. If a \
character is unnamed, invent a descriptive key like "stranger" or "the_voice".
- Give each character a distinct voice_profile that a voice actor could use \
for casting — include gender, age range, emotional quality, and any speech \
patterns.

Text Adaptation:
- Rewrite narration lines for spoken performance — break up dense paragraphs, \
adjust punctuation for natural breathing pauses.
- Do NOT add content that isn't in the original story. You are adapting, \
not inventing.
- Smooth transitions between multi-part story sections.
- Convert any remaining Reddit-isms into natural prose.

Output ONLY the JSON object, no commentary before or after it.\
"""


def generate_script(
    title: str,
    narration_text: str,
    prior_characters: dict | None = None,
) -> NarrationScript:
    """Use Claude to transform cleaned story text into a dramatic narration script.

    For stories that exceed a comfortable processing length, the text is split
    into sections and processed sequentially so that character assignments and
    tone stay consistent across the whole story.

    *prior_characters*, when provided, seeds the first section with character
    definitions from earlier parts of a series so that voices stay consistent
    across separately-generated parts.
    """
    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    sections = _split_for_adaptation(narration_text)

    if len(sections) == 1:
        try:
            script = _adapt_section(client, title, sections[0], prior_characters=prior_characters)
        except _TruncatedResponseError:
            logger.info(
                "Single section truncated for '%s', re-splitting into smaller pieces",
                title,
            )
            sections = _split_for_adaptation(narration_text, max_chars=6000)
            script = _adapt_long_story(client, title, sections, prior_characters=prior_characters)
    else:
        script = _adapt_long_story(client, title, sections, prior_characters=prior_characters)

    return script


def _adapt_section(
    client: Anthropic,
    title: str,
    text: str,
    prior_characters: dict | None = None,
) -> NarrationScript:
    """Process a single section of text into a narration script."""

    user_prompt = f'Story title: "{title}"\n\n{text}'

    if prior_characters:
        user_prompt += (
            "\n\nIMPORTANT: This is a continuation. Reuse these existing "
            f"character definitions:\n{json.dumps(prior_characters, indent=2)}"
        )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=MAX_OUTPUT_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    # Detect truncated output *before* attempting JSON parse.  When the
    # response is cut off mid-token the JSON will always be invalid, so
    # there is no point trying to parse it — signal the caller to retry
    # with a smaller input section instead.
    if response.stop_reason == "max_tokens":
        logger.warning(
            "Claude response truncated (max_tokens) for '%s'; "
            "input section may be too long for a single request",
            title,
        )
        raise _TruncatedResponseError(title)

    raw_text = response.content[0].text.strip()
    # Strip markdown code fences if present
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[1]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3].strip()

    try:
        script_data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.error("Claude returned invalid JSON for '%s': %s", title, raw_text[:500])
        raise ValueError(
            f"Script generation failed: Claude did not return valid JSON ({exc})"
        ) from exc

    return NarrationScript(**script_data)


def _adapt_long_story(
    client: Anthropic,
    title: str,
    sections: list[str],
    prior_characters: dict | None = None,
) -> NarrationScript:
    """Process a multi-section story by adapting each section sequentially,
    carrying character definitions forward for consistency.

    If any individual section causes a truncated response, it is
    automatically split in half and the sub-sections are retried.

    *prior_characters*, when provided, seeds the character map so the first
    section already knows about characters from earlier series parts.
    """

    MAX_ITERATIONS = 50  # safety limit to prevent runaway splitting

    combined_characters: dict = dict(prior_characters) if prior_characters else {}
    all_segments: list[dict] = []

    # Use a queue so truncated sections can be split and re-inserted.
    pending = list(sections)
    processed = 0
    iterations = 0

    while pending:
        iterations += 1
        if iterations > MAX_ITERATIONS:
            raise ValueError(
                f"Story '{title}' required too many sections to process "
                f"(exceeded {MAX_ITERATIONS})"
            )

        section = pending.pop(0)
        processed += 1
        logger.info("Adapting section %d of '%s'", processed, title)

        try:
            script = _adapt_section(
                client, title, section,
                prior_characters=combined_characters if combined_characters else None,
            )
        except _TruncatedResponseError:
            # This section's output exceeded max_tokens.  Split it and
            # prepend the halves back onto the queue for retry.
            logger.info(
                "Section %d of '%s' truncated, splitting further",
                processed, title,
            )
            halves = _split_for_adaptation(section, max_chars=len(section) // 2)
            pending = halves + pending
            processed -= 1  # don't count the failed attempt
            continue

        # Merge characters (later sections may introduce new ones)
        combined_characters.update(
            {k: v.model_dump() for k, v in script.characters.items()}
        )

        # Add a scene transition pause between sections (not before the first)
        if all_segments:
            all_segments.append({"type": "pause", "duration_ms": 2000})

        all_segments.extend([s.model_dump() for s in script.segments])

    final_characters = {
        k: CharacterProfile(**v) for k, v in combined_characters.items()
    }

    return NarrationScript(
        title=title,
        characters=final_characters,
        segments=[ScriptSegment(**s) for s in all_segments],
    )


def _split_for_adaptation(text: str, max_chars: int = 12000) -> list[str]:
    """Split long text into sections for sequential adaptation.

    Splits on paragraph boundaries, keeping each section under *max_chars*
    where possible.  Single paragraphs that exceed the limit are kept
    intact (they cannot be split further without breaking sentences).
    """
    if len(text) <= max_chars:
        return [text]

    paragraphs = text.split("\n\n")
    sections: list[str] = []
    current = ""

    for para in paragraphs:
        candidate = f"{current}\n\n{para}".strip() if current else para
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                sections.append(current)
            current = para

    if current:
        sections.append(current)

    return sections if sections else [text]
