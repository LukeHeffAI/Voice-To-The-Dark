"""Thread-based background task runner for generation tasks.

Spawns daemon threads to run script/narration generation in the background,
updating the GenerationTask model with progress as the work proceeds.
"""

import logging
import threading
from urllib.parse import urlparse

from django.db import close_old_connections
from django.utils import timezone

from apps.audio.models import GenerationTask
from apps.audio.schemas import NarrationScript
from apps.audio.services.narration_generator import generate_narration
from apps.audio.services.script_adapter import generate_script
from apps.audio.services.voice_pool import auto_assign_voices
from apps.stories.models import Story

logger = logging.getLogger(__name__)


def _update_progress(task_id: int, progress: int, stage: str) -> None:
    """Update task progress in the database (thread-safe)."""
    GenerationTask.objects.filter(id=task_id).update(
        progress=progress,
        stage=stage,
    )


def _collect_series_characters(story: Story) -> dict | None:
    """Merge character definitions from earlier parts of the same series."""
    if not story.series_json:
        return None

    series_parts = story.series_json
    if not isinstance(series_parts, list):
        return None

    current_url = (story.reddit_url or "").rstrip("/")
    current_created = None
    for part in series_parts:
        part_url = (part.get("url") or "").rstrip("/")
        pa = urlparse(current_url)
        pb = urlparse(part_url)
        na = pa.netloc.lower().removeprefix("www.")
        nb = pb.netloc.lower().removeprefix("www.")
        if na == nb and pa.path.rstrip("/") == pb.path.rstrip("/"):
            current_created = part.get("created_utc", 0)
            break

    if current_created is None:
        return None

    earlier_urls = []
    for part in series_parts:
        if part.get("created_utc", 0) < current_created:
            url = (part.get("url") or "").strip()
            if url:
                earlier_urls.append(url)

    if not earlier_urls:
        return None

    candidate_urls = set()
    for url in earlier_urls:
        base = url.rstrip("/")
        candidate_urls.add(base)
        candidate_urls.add(base + "/")
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            alt = netloc[4:] if netloc.startswith("www.") else "www." + netloc
            alt_url = parsed._replace(netloc=alt).geturl().rstrip("/")
            candidate_urls.add(alt_url)
            candidate_urls.add(alt_url + "/")
        except Exception:
            pass

    earlier_stories = list(
        Story.objects.filter(reddit_url__in=candidate_urls).exclude(script_json__isnull=True)
    )

    if not earlier_stories:
        return None

    url_to_created = {}
    for part in series_parts:
        pu = (part.get("url") or "").rstrip("/")
        p = urlparse(pu)
        key = (p.netloc.lower().removeprefix("www."), p.path.rstrip("/"))
        url_to_created[key] = part.get("created_utc", 0)

    def _sort_key(s: Story) -> float:
        p = urlparse((s.reddit_url or "").rstrip("/"))
        key = (p.netloc.lower().removeprefix("www."), p.path.rstrip("/"))
        return url_to_created.get(key, 0)

    earlier_stories.sort(key=_sort_key)

    merged: dict = {}
    for s in earlier_stories:
        try:
            script = NarrationScript(**s.script_json)
            merged.update({k: v.model_dump() for k, v in script.characters.items()})
        except Exception:
            continue

    return merged if merged else None


def _run_script_task(task_id: int) -> None:
    """Background thread target for script generation."""
    try:
        close_old_connections()

        task = GenerationTask.objects.select_related("story").get(id=task_id)
        task.status = "running"
        task.started_at = timezone.now()
        task.save(update_fields=["status", "started_at"])

        story = task.story
        text = story.narration_text or story.text_content
        if not text:
            raise ValueError("Story has no text to adapt")

        prior_characters = _collect_series_characters(story)

        def progress_cb(progress: int, stage: str) -> None:
            _update_progress(task_id, progress, stage)

        script = generate_script(
            story.title, text,
            prior_characters=prior_characters,
            progress_callback=progress_cb,
        )

        # Save result to story
        story.script_json = script.model_dump()
        story.save(update_fields=["script_json"])

        # Mark task complete
        task.status = "completed"
        task.progress = 100
        task.stage = "Script complete"
        task.completed_at = timezone.now()
        task.result_json = {
            "message": "Script generated successfully!",
            "characters": script.character_names(),
        }
        task.save(update_fields=["status", "progress", "stage", "completed_at", "result_json"])

    except Exception as exc:
        logger.exception("Script generation task %s failed", task_id)
        GenerationTask.objects.filter(id=task_id).update(
            status="failed",
            error_message=str(exc),
            completed_at=timezone.now(),
        )
    finally:
        close_old_connections()


def _run_narration_task(task_id: int, voice_map: dict[str, str], bust_cache: bool) -> None:
    """Background thread target for narration generation."""
    import os

    try:
        close_old_connections()

        task = GenerationTask.objects.select_related("story").get(id=task_id)
        task.status = "running"
        task.started_at = timezone.now()
        task.save(update_fields=["status", "started_at"])

        story = task.story

        if not story.script_json:
            raise ValueError("No script found. Generate a script first.")

        script = NarrationScript(**story.script_json)

        # Persist voice IDs into character profiles
        for char_name, voice_id in voice_map.items():
            if char_name in script.characters:
                script.characters[char_name].voice_id = voice_id
        story.script_json = script.model_dump()

        # Clean up old audio file
        if story.audio_file_path:
            try:
                if os.path.exists(story.audio_file_path):
                    os.remove(story.audio_file_path)
            except Exception:
                logger.warning("Failed to delete old audio: %s", story.audio_file_path, exc_info=True)
            story.audio_file_path = None

        story.save(update_fields=["script_json", "audio_file_path"])

        def progress_cb(progress: int, stage: str) -> None:
            _update_progress(task_id, progress, stage)

        result = generate_narration(
            script, voice_map,
            bust_cache=bust_cache,
            progress_callback=progress_cb,
        )

        # Save result to story
        story.audio_file_path = result.output_path
        story.save(update_fields=["audio_file_path"])

        # Mark task complete
        task.status = "completed"
        task.progress = 100
        task.stage = "Audio ready"
        task.completed_at = timezone.now()
        task.result_json = {
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
        task.save(update_fields=["status", "progress", "stage", "completed_at", "result_json"])

    except Exception as exc:
        logger.exception("Narration generation task %s failed", task_id)
        GenerationTask.objects.filter(id=task_id).update(
            status="failed",
            error_message=str(exc),
            completed_at=timezone.now(),
        )
    finally:
        close_old_connections()


def start_script_generation(task: GenerationTask) -> None:
    """Spawn a background thread to run script generation."""
    thread = threading.Thread(
        target=_run_script_task,
        args=(task.id,),
        daemon=True,
        name=f"script-gen-{task.id}",
    )
    thread.start()


def start_narration_generation(
    task: GenerationTask,
    voice_map: dict[str, str],
    bust_cache: bool = False,
) -> None:
    """Spawn a background thread to run narration generation."""
    thread = threading.Thread(
        target=_run_narration_task,
        args=(task.id, voice_map, bust_cache),
        daemon=True,
        name=f"narration-gen-{task.id}",
    )
    thread.start()
