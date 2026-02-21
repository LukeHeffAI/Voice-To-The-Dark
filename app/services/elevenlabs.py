import os
import uuid
import requests
from typing import List
from app.config import settings
from app.services.audio_utils import stitch_audio_files, create_tmp_folder, cleanup_temp_files

# ElevenLabs can handle a certain character limit at once (e.g., 5k-10k).
# We'll define a chunk size. Adjust as needed or do advanced chunking by sentences.
MAX_TEXT_LENGTH = 4900  # safe margin

def generate_audio(
    text: str,
    voice_id: str,
    output_path: str = None
) -> str:
    """
    Generates an audio file for the given text using ElevenLabs API.
    Splits the text into chunks if it exceeds the max chunk size.
    Stitches them together, returns the final file path.
    """
    if not output_path:
        output_path = f"./stories/{uuid.uuid4()}.mp3"

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    tmp_folder = create_tmp_folder()  # ensure tmp/ exists
    chunks = chunk_text(text, MAX_TEXT_LENGTH)

    audio_chunks = []
    for idx, chunk in enumerate(chunks):
        tmp_file_name = f"chunk_{uuid.uuid4()}.mp3"
        chunk_output = os.path.join(tmp_folder, tmp_file_name)
        tts_request(chunk, voice_id, chunk_output)
        audio_chunks.append(chunk_output)

    if len(audio_chunks) > 1:
        stitch_audio_files(audio_chunks, output_path)
        # cleanup chunk files
        for f in audio_chunks:
            try:
                os.remove(f)
            except:
                pass
    else:
        os.rename(audio_chunks[0], output_path)

    # Possibly call cleanup_temp_files to clean up any older leftover files
    cleanup_temp_files(tmp_folder, days=3)

    return output_path


def chunk_text(text: str, max_len: int) -> List[str]:
    """
    Splits text into smaller pieces, each <= max_len chars.
    You might want more sophisticated splits by sentence boundaries, etc.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_len, len(text))
        chunks.append(text[start:end])
        start = end
    return chunks


def tts_request(text: str, voice_id: str, output_file: str):
    """
    Calls the ElevenLabs TTS API to generate audio for a single text chunk.
    Saves it to `output_file`.
    """
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
    headers = {
        "xi-api-key": settings.ELEVENLABS_API_KEY,
        "Accept": "audio/mpeg",
        "Content-Type": "application/json"
    }
    data = {
        "text": text,
        "voice_settings": {
            # Optional voice settings
            # e.g. "stability": 0.5,
            # "similarity_boost": 0.75
        }
    }

    response = requests.post(url, headers=headers, json=data, stream=True)
    response.raise_for_status()  # will throw if error from API

    with open(output_file, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
