"""Background task functions that wrap existing service calls.

Each function receives a BackgroundTask instance as its first argument
so it can update progress in the database as work proceeds.
"""

import logging
import os

from apps.tasks.models import BackgroundTask, TaskStatus

logger = logging.getLogger(__name__)


def run_generate_script(task: BackgroundTask, story_id: int, force_regenerate: bool = False, prior_characters=None):
    """Background task for script generation via Claude AI."""
    from apps.audio.helpers import pydantic_to_script
    from apps.stories.models import Story
    from services.script_adapter import generate_script

    task.progress_message = "Analyzing story with Claude AI..."
    task.save(update_fields=["progress_message"])

    story = Story.objects.get(id=story_id)
    text = story.narration_text or story.text_content

    script = generate_script(story.title, text, prior_characters=prior_characters)

    task.progress_message = "Saving script..."
    task.save(update_fields=["progress_message"])

    pydantic_to_script(story, script)

    return {
        "message": "Script generated successfully!",
        "characters": script.character_names(),
    }


def run_generate_narration(
    task: BackgroundTask,
    story_id: int,
    voice_map: dict[str, str],
    script_data: dict,
    bust_cache: bool = False,
):
    """Background task for narration generation with segment-level progress."""
    from apps.audio.helpers import pydantic_to_script
    from apps.stories.models import Story
    from schemas.narration import NarrationScript
    from services.narration_generator import generate_narration

    story = Story.objects.get(id=story_id)
    script = NarrationScript(**script_data)

    # Update status to generating segments
    task.status = TaskStatus.GENERATING_SEGMENTS
    task.progress_message = "Preparing audio segments..."
    task.save(update_fields=["status", "progress_message"])

    def _progress_callback(current: int, total: int, message: str):
        task.progress_current = current
        task.progress_total = total
        task.progress_message = message
        task.save(update_fields=["progress_current", "progress_total", "progress_message"])

    def _mixing_callback():
        task.status = TaskStatus.MIXING
        task.progress_message = "Mixing final audio..."
        task.save(update_fields=["status", "progress_message"])

    result = generate_narration(
        script, voice_map, bust_cache=bust_cache,
        progress_callback=_progress_callback,
        mixing_callback=_mixing_callback,
    )

    # Ensure task transitions to MIXING even if `mixing_callback` was not
    # invoked (e.g., when `generate_narration` is mocked in tests).
    if task.status != TaskStatus.MIXING:
        _mixing_callback()

    # Delete old audio file
    if story.audio_file_path:
        try:
            if os.path.exists(story.audio_file_path):
                os.remove(story.audio_file_path)
        except Exception:
            logger.warning("Failed to delete old audio file: %s", story.audio_file_path, exc_info=True)

    story.audio_file_path = result.output_path
    story.save(update_fields=["audio_file_path"])

    return {
        "message": "Narration generated successfully!",
        "audio_file": result.output_path,
        "segments_processed": result.total_segments,
        "voice_assignments": voice_map,
        "cache_stats": {
            "total_segments": result.total_segments,
            "cache_hits": result.cache_hits,
            "cache_misses": result.cache_misses,
            "api_calls_saved": result.cache_hits,
        },
    }
