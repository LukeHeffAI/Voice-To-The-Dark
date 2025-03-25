# app/services/audio_utils.py

from pydub import AudioSegment
import os
import time
import shutil
import logging
from datetime import datetime, timedelta

def stitch_audio_files(file_paths: list, output_path: str):
    """
    Concatenate multiple audio files (MP3) into one seamless audio segment.
    Export to the desired output_path (mp3).
    """
    if not file_paths:
        return

    # Initialize with the first file
    combined = AudioSegment.from_file(file_paths[0], format="mp3")

    # Append the rest
    for fp in file_paths[1:]:
        segment = AudioSegment.from_file(fp, format="mp3")
        combined += segment

    # Export as mp3
    combined.export(output_path, format="mp3")

def create_tmp_folder():
    """
    Ensure 'tmp/' folder exists at the root of the app for storing chunk files.
    """
    tmp_path = os.path.join(os.getcwd(), "tmp")
    if not os.path.exists(tmp_path):
        os.makedirs(tmp_path)
    return tmp_path

def cleanup_temp_files(folder: str = None, days: int = 7):
    """
    Delete any files in `folder` older than `days` days.
    If folder is None, default to 'tmp/' in the current working directory.
    """
    if not folder:
        folder = os.path.join(os.getcwd(), "tmp")

    if not os.path.isdir(folder):
        return  # nothing to do

    now = time.time()
    age_threshold = days * 86400  # days in seconds

    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        if os.path.isfile(file_path):
            # check age
            file_age = now - os.path.getmtime(file_path)
            if file_age > age_threshold:
                try:
                    os.remove(file_path)
                    logging.info(f"Removed old temp file: {file_path}")
                except Exception as e:
                    logging.warning(f"Could not remove {file_path}: {e}")

def purge_temp_folder(folder: str = None):
    """
    Completely wipe the tmp folder (if you ever need a full reset).
    """
    if not folder:
        folder = os.path.join(os.getcwd(), "tmp")
    try:
        shutil.rmtree(folder)
        logging.info(f"Purged temp folder: {folder}")
    except Exception as e:
        logging.warning(f"Could not purge {folder}: {e}")
    finally:
        create_tmp_folder()  # Recreate empty folder
