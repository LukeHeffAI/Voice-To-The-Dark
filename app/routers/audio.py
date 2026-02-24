import json
import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.elevenlabs import generate_audio
from app.services.script_adapter import generate_script
from app.services.narration_generator import generate_narration
from app.models.story import Story
from app.schemas.story import GenerateScriptRequest, GenerateNarrationRequest
from app.schemas.narration import NarrationScript
from app.services.voice_pool import auto_assign_voices
from app.models.story import User
from app.deps import get_current_user
from app.rate_limit import rate_limit

logger = logging.getLogger(__name__)

router = APIRouter()


class GenerateAudioRequest(BaseModel):
    story_id: int
    voice_id: str
    force_regenerate: bool = False


@router.post("/generate-audio")
def generate_audio_route(req: GenerateAudioRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Generate basic TTS audio from the cleaned narration text (flat, single voice)."""
    story = db.query(Story).filter(Story.id == req.story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    if story.audio_file_path and not req.force_regenerate:
        return {"message": "Already generated", "audio_file": story.audio_file_path}

    tts_text = story.narration_text or story.text_content
    new_audio_path = generate_audio(tts_text, req.voice_id)
    story.audio_file_path = new_audio_path
    db.commit()
    db.refresh(story)

    return {
        "message": "Audio generated successfully!",
        "audio_file": story.audio_file_path,
    }


@router.post("/generate-script")
def generate_script_route(req: GenerateScriptRequest, _rl=Depends(rate_limit(10, 3600)), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Use Claude to transform a story into a dramatic narration script.

    The script identifies characters, adds SFX/ambient cues, emotional tone
    markers, and pacing pauses. It can be previewed and edited before
    committing to audio generation.
    """
    story = db.query(Story).filter(Story.id == req.story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    if story.script_json and not req.force_regenerate:
        script = NarrationScript(**json.loads(story.script_json))
        return {
            "message": "Script already exists",
            "script": script.model_dump(),
            "characters": script.character_names(),
        }

    text = story.narration_text or story.text_content
    if not text:
        raise HTTPException(status_code=400, detail="Story has no text to adapt")

    try:
        script = generate_script(story.title, text)
    except Exception as exc:
        logger.exception("Script generation failed for story %s", req.story_id)
        raise HTTPException(
            status_code=502,
            detail=f"Script generation failed: {exc}",
        ) from exc

    story.script_json = json.dumps(script.model_dump())
    db.commit()
    db.refresh(story)

    return {
        "message": "Script generated successfully!",
        "script": script.model_dump(),
        "characters": script.character_names(),
    }


@router.get("/script/{story_id}")
def get_script(story_id: int, db: Session = Depends(get_db)):
    """Retrieve the narration script for a story so it can be previewed or edited."""
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    if not story.script_json:
        raise HTTPException(status_code=404, detail="No script generated for this story yet")

    script = NarrationScript(**json.loads(story.script_json))
    return {
        "script": script.model_dump(),
        "characters": script.character_names(),
        "segment_count": len(script.segments),
        "voice_segments": len(script.voice_segments()),
        "sfx_segments": len(script.sfx_segments()),
    }


@router.put("/script/{story_id}")
def update_script(story_id: int, script_data: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Update/edit the narration script before generating audio.

    Accepts the full script JSON so the user can tweak character assignments,
    adjust SFX cues, modify tone directions, etc.
    """
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    # Validate the script structure
    script = NarrationScript(**script_data)

    story.script_json = json.dumps(script.model_dump())
    db.commit()

    return {"message": "Script updated", "characters": script.character_names()}


@router.post("/generate-narration")
def generate_narration_route(req: GenerateNarrationRequest, _rl=Depends(rate_limit(5, 3600)), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Generate the full dramatic narration: multi-voice TTS + SFX + ambient + mixing.

    Requires a script to have been generated first (via /generate-script).
    If voice_map is omitted, voices are auto-assigned from a diverse pool
    based on each character's voice_profile description.
    """
    story = db.query(Story).filter(Story.id == req.story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    if story.audio_file_path and not req.force_regenerate:
        return {"message": "Already generated", "audio_file": story.audio_file_path}

    if not story.script_json:
        raise HTTPException(
            status_code=400,
            detail="No script found. Generate a script first with /generate-script",
        )

    script = NarrationScript(**json.loads(story.script_json))

    # Auto-assign voices if no voice_map provided
    voice_map = req.voice_map
    if not voice_map:
        voice_map = auto_assign_voices(script.characters)
        logger.info(f"Auto-assigned voices: {voice_map}")
    else:
        # Validate that all characters have a voice assignment
        missing = [c for c in script.character_names() if c not in voice_map]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Missing voice assignments for characters: {missing}. "
                       f"Required characters: {script.character_names()}",
            )

    audio_path = generate_narration(script, voice_map)

    story.audio_file_path = audio_path
    db.commit()
    db.refresh(story)

    return {
        "message": "Narration generated successfully!",
        "audio_file": story.audio_file_path,
        "segments_processed": len(script.segments),
        "voice_assignments": voice_map,
    }
