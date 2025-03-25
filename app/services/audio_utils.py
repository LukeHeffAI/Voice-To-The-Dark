from pydub import AudioSegment
import os

def stitch_audio_files(file_paths: list, output_path: str):
    """
    Concatenate multiple audio files into one seamless audio segment.
    Export to the desired output_path (mp3).
    """
    if not file_paths:
        return

    # Initialise with the first file
    combined = AudioSegment.from_file(file_paths[0], format="mp3")

    # Append the rest
    for fp in file_paths[1:]:
        segment = AudioSegment.from_file(fp, format="mp3")
        combined += segment

    # Export as mp3
    combined.export(output_path, format="mp3")
