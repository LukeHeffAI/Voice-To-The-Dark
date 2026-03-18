import os

from django.http import FileResponse, StreamingHttpResponse
from ninja import Router
from ninja.errors import HttpError

from apps.stories.models import Story

router = Router(tags=["player"])


@router.get("/story-info/{story_id}")
def story_info(request, story_id: int):
    """Lightweight JSON endpoint returning basic story metadata."""
    story = Story.objects.filter(id=story_id).first()
    if not story:
        raise HttpError(404, "Story not found")
    return {
        "id": story.id,
        "title": story.title,
        "author": story.author,
        "part_count": story.part_count,
        "has_audio": bool(story.audio_file_path),
    }


@router.get("/stream/{story_id}")
def stream_audio(request, story_id: int):
    """Stream the audio file for a story with HTTP Range request support.

    Range requests are essential for:
    - Mobile browsers seeking within audio
    - Lock-screen playback on Android
    - Resuming from a saved position without downloading the whole file
    """
    story = Story.objects.filter(id=story_id).first()
    if not story or not story.audio_file_path:
        raise HttpError(404, "Audio not found")

    file_path = story.audio_file_path
    if not os.path.isfile(file_path):
        raise HttpError(404, "Audio file missing from disk")

    file_size = os.path.getsize(file_path)
    range_header = request.headers.get("Range")

    if range_header:
        # Validate Range header format
        if not range_header.startswith("bytes="):
            raise HttpError(416, "Invalid Range header")

        range_spec = range_header[6:].strip()

        # Reject multi-range requests
        if "," in range_spec:
            raise HttpError(416, "Multi-range requests are not supported")

        parts = range_spec.split("-", 1)
        if len(parts) != 2:
            raise HttpError(416, "Invalid Range format")

        try:
            if parts[0] == "":
                # Suffix range: bytes=-500 (last 500 bytes)
                suffix_length = int(parts[1])
                if suffix_length <= 0:
                    raise HttpError(416, "Invalid suffix range")
                start = max(0, file_size - suffix_length)
                end = file_size - 1
            elif parts[1] == "":
                # Open-ended range: bytes=500-
                start = int(parts[0])
                end = file_size - 1
            else:
                # Standard range: bytes=0-499
                start = int(parts[0])
                end = int(parts[1])
        except ValueError:
            raise HttpError(416, "Invalid Range values")

        # Validate bounds
        if start < 0 or start >= file_size or end < start:
            raise HttpError(416, "Range not satisfiable")

        # Clamp end to file bounds
        end = min(end, file_size - 1)
        content_length = end - start + 1

        def iter_range():
            with open(file_path, "rb") as f:
                f.seek(start)
                remaining = content_length
                while remaining > 0:
                    chunk_size = min(8192, remaining)
                    data = f.read(chunk_size)
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        response = StreamingHttpResponse(
            iter_range(),
            status=206,
            content_type="audio/mpeg",
        )
        response["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        response["Accept-Ranges"] = "bytes"
        response["Content-Length"] = str(content_length)
        response["Cache-Control"] = "public, max-age=86400"
        return response

    # No range header — serve the full file
    response = FileResponse(
        open(file_path, "rb"),
        content_type="audio/mpeg",
    )
    response["Accept-Ranges"] = "bytes"
    response["Content-Length"] = str(file_size)
    response["Cache-Control"] = "public, max-age=86400"
    return response


@router.get("/download/{story_id}")
def download_audio(request, story_id: int):
    """Download the audio file for a story."""
    story = Story.objects.filter(id=story_id).first()
    if not story or not story.audio_file_path:
        raise HttpError(404, "Audio not found")

    file_path = story.audio_file_path
    if not os.path.isfile(file_path):
        raise HttpError(404, "Audio file missing from disk")

    safe_title = "".join(c for c in story.title if c.isalnum() or c in " -_").strip()
    filename = f"{safe_title}.mp3"

    response = FileResponse(
        open(file_path, "rb"),
        content_type="audio/mpeg",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
