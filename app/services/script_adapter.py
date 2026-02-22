import json
import logging
from anthropic import Anthropic
from app.config import settings
from app.schemas.narration import NarrationScript, CharacterProfile, ScriptSegment

logger = logging.getLogger(__name__)

# Claude's output token limit per request. If the story is very long we
# process it in sections and stitch the scripts together.
MAX_OUTPUT_TOKENS = 8192

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


def generate_script(title: str, narration_text: str) -> NarrationScript:
    """Use Claude to transform cleaned story text into a dramatic narration script.

    For stories that exceed a comfortable processing length, the text is split
    into sections and processed sequentially so that character assignments and
    tone stay consistent across the whole story.
    """
    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    sections = _split_for_adaptation(narration_text)

    if len(sections) == 1:
        script = _adapt_section(client, title, sections[0])
    else:
        script = _adapt_long_story(client, title, sections)

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
        model="claude-sonnet-4-20250514",
        max_tokens=MAX_OUTPUT_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw_text = response.content[0].text.strip()
    # Strip markdown code fences if present
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[1]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3].strip()

    script_data = json.loads(raw_text)
    return NarrationScript(**script_data)


def _adapt_long_story(
    client: Anthropic,
    title: str,
    sections: list[str],
) -> NarrationScript:
    """Process a multi-section story by adapting each section sequentially,
    carrying character definitions forward for consistency."""

    combined_characters = {}
    all_segments = []

    for i, section in enumerate(sections):
        logger.info(f"Adapting section {i + 1}/{len(sections)} of '{title}'")

        script = _adapt_section(
            client, title, section,
            prior_characters=combined_characters if combined_characters else None,
        )

        # Merge characters (later sections may introduce new ones)
        combined_characters.update(
            {k: v.model_dump() for k, v in script.characters.items()}
        )

        # Add a scene transition pause between sections (not before the first)
        if i > 0 and all_segments:
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

    Splits on paragraph boundaries (double newlines) and keeps each section
    under max_chars. This ensures Claude has enough output headroom to produce
    a detailed script for each section.
    """
    if len(text) <= max_chars:
        return [text]

    paragraphs = text.split("\n\n")
    sections = []
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

    return sections
