"""Helpers for converting between Django ORM script models and Pydantic schemas.

The services layer uses Pydantic NarrationScript objects, but the Django ORM
stores scripts in relational tables (NarrationScript, Character, ScriptSegment).
These helpers bridge the two representations.
"""

from apps.audio.models import Character, NarrationScript, ScriptSegment
from apps.stories.models import Story
from schemas.narration import (
    CharacterProfile,
    NarrationScript as NarrationScriptSchema,
    ScriptSegment as ScriptSegmentSchema,
    SegmentType,
)


def script_to_pydantic(db_script: NarrationScript) -> NarrationScriptSchema:
    """Convert a Django ORM NarrationScript to a Pydantic NarrationScript."""
    characters = {}
    for char in db_script.characters.all():
        characters[char.name] = CharacterProfile(
            voice_profile=char.voice_profile,
            voice_id=char.voice_id or None,
        )

    segments = []
    # Build a name lookup for character FK resolution
    char_id_to_name = {char.id: char.name for char in db_script.characters.all()}

    for seg in db_script.segments.order_by("order"):
        segment = ScriptSegmentSchema(
            type=SegmentType(seg.type),
            character=char_id_to_name.get(seg.character_id) if seg.character_id else None,
            text=seg.text or None,
            tone=seg.tone or None,
            description=seg.description or None,
            duration_ms=seg.duration_ms,
            loop=seg.loop,
        )
        segments.append(segment)

    return NarrationScriptSchema(
        title=db_script.title,
        characters=characters,
        segments=segments,
    )


def pydantic_to_script(story: Story, schema: NarrationScriptSchema) -> NarrationScript:
    """Save a Pydantic NarrationScript to Django ORM models.

    Creates or replaces the NarrationScript, Characters, and ScriptSegments
    for the given story.
    """
    # Delete existing script if any
    NarrationScript.objects.filter(story=story).delete()

    db_script = NarrationScript.objects.create(
        story=story,
        title=schema.title,
    )

    # Create characters
    char_objects = {}
    for name, profile in schema.characters.items():
        char_obj = Character.objects.create(
            script=db_script,
            name=name,
            voice_profile=profile.voice_profile,
            voice_id=profile.voice_id or "",
        )
        char_objects[name] = char_obj

    # Create segments
    segments_to_create = []
    for order, seg in enumerate(schema.segments):
        char_obj = char_objects.get(seg.character) if seg.character else None
        segments_to_create.append(
            ScriptSegment(
                script=db_script,
                order=order,
                type=seg.type.value,
                character=char_obj,
                text=seg.text or "",
                tone=seg.tone or "",
                description=seg.description or "",
                duration_ms=seg.duration_ms,
                loop=seg.loop,
            )
        )
    ScriptSegment.objects.bulk_create(segments_to_create)

    return db_script
