from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.services.elevenlabs import generate_audio
from app.models.story import Story
import os

router = APIRouter()

class GenerateAudioRequest(BaseModel):
    story_id: int
    voice_id: str
    force_regenerate: bool = False

@router.post("/generate-audio")
def generate_audio_route(req: GenerateAudioRequest):
    # DB session
    db: Session = SessionLocal()
    story = db.query(Story).filter(Story.id == req.story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    # Check if audio already exists
    if story.audio_file_path and not req.force_regenerate:
        # Return existing path or direct user to it
        return {"message": "Already generated", "audio_file": story.audio_file_path}
    
    # Generate new audio
    new_audio_path = generate_audio(story.text_content, req.voice_id)
    # Save to DB
    story.audio_file_path = new_audio_path
    db.commit()
    db.refresh(story)

    return {
        "message": "Audio generated successfully!",
        "audio_file": story.audio_file_path
    }
