from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.elevenlabs import generate_audio
from app.models.story import Story

router = APIRouter()


class GenerateAudioRequest(BaseModel):
    story_id: int
    voice_id: str
    force_regenerate: bool = False


@router.post("/generate-audio")
def generate_audio_route(req: GenerateAudioRequest, db: Session = Depends(get_db)):
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
        "audio_file": story.audio_file_path
    }
