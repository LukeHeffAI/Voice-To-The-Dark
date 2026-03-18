"""Unit tests for the apps.audio.task_runner module.

Tests cover:
- _update_progress: DB progress/stage updates
- _run_script_task: script generation lifecycle (success, failure, edge cases)
- _run_narration_task: narration generation lifecycle (success, failure, edge cases)
- _collect_series_characters: merging character defs from earlier series parts
"""

import pytest
from unittest.mock import MagicMock, patch

from apps.accounts.models import User
from apps.audio.models import GenerationTask
from apps.audio.schemas import (
    CharacterProfile,
    NarrationScript,
    ScriptSegment,
    SegmentType,
)
from apps.stories.models import Story

from apps.audio.task_runner import (
    _collect_series_characters,
    _run_narration_task,
    _run_script_task,
    _update_progress,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def user(db):
    return User.objects.create_user(username="runner_user", password="pass123")


@pytest.fixture()
def story(db):
    return Story.objects.create(
        title="Test Story",
        text_content="A dark and stormy night.",
        narration_text="A dark and stormy night.",
        content_hash="runner_hash_123",
    )


@pytest.fixture()
def script_task(db, user, story):
    return GenerationTask.objects.create(
        user=user,
        story=story,
        task_type="script",
        status="queued",
        stage="Queued",
    )


@pytest.fixture()
def narration_task(db, user, story):
    story.script_json = {
        "title": "Test",
        "characters": {"Narrator": {"voice_profile": "deep"}},
        "segments": [{"type": "narration", "character": "Narrator", "text": "Hello"}],
    }
    story.save()
    return GenerationTask.objects.create(
        user=user,
        story=story,
        task_type="narration",
        status="queued",
        stage="Queued",
    )


def _make_mock_script():
    """Return a NarrationScript suitable for mocking generate_script."""
    return NarrationScript(
        title="Test",
        characters={"Narrator": CharacterProfile(voice_profile="deep")},
        segments=[
            ScriptSegment(type=SegmentType.NARRATION, character="Narrator", text="Hello"),
        ],
    )


def _make_mock_narration_result():
    """Return a mock result object for generate_narration."""
    result = MagicMock()
    result.output_path = "/tmp/test_audio.mp3"
    result.total_segments = 5
    result.cache_hits = 2
    result.cache_misses = 3
    return result


# ---------------------------------------------------------------------------
# TestUpdateProgress
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestUpdateProgress:
    def test_updates_progress(self, script_task):
        _update_progress(script_task.id, 42, "Working")
        script_task.refresh_from_db()
        assert script_task.progress == 42

    def test_updates_stage(self, script_task):
        _update_progress(script_task.id, 10, "Adapting script")
        script_task.refresh_from_db()
        assert script_task.stage == "Adapting script"


# ---------------------------------------------------------------------------
# TestRunScriptTask
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestRunScriptTask:

    @patch("apps.audio.task_runner.close_old_connections")
    @patch("apps.audio.task_runner.generate_script")
    def test_success(self, mock_gen, mock_close, script_task, story):
        mock_gen.return_value = _make_mock_script()

        _run_script_task(script_task.id)

        script_task.refresh_from_db()
        story.refresh_from_db()

        assert script_task.status == "completed"
        assert script_task.progress == 100
        assert story.script_json is not None
        assert "characters" in script_task.result_json

    @patch("apps.audio.task_runner.close_old_connections")
    @patch("apps.audio.task_runner.generate_script")
    def test_failure(self, mock_gen, mock_close, script_task):
        mock_gen.side_effect = RuntimeError("API is down")

        _run_script_task(script_task.id)

        script_task.refresh_from_db()
        assert script_task.status == "failed"
        assert "API is down" in script_task.error_message

    @patch("apps.audio.task_runner.close_old_connections")
    @patch("apps.audio.task_runner.generate_script")
    def test_no_text(self, mock_gen, mock_close, user, db):
        empty_story = Story.objects.create(
            title="Empty",
            text_content="",
            narration_text="",
            content_hash="empty_hash_456",
        )
        task = GenerationTask.objects.create(
            user=user,
            story=empty_story,
            task_type="script",
            status="queued",
            stage="Queued",
        )

        _run_script_task(task.id)

        task.refresh_from_db()
        assert task.status == "failed"
        assert "no text" in task.error_message.lower()
        mock_gen.assert_not_called()

    @patch("apps.audio.task_runner.close_old_connections")
    @patch("apps.audio.task_runner.generate_script")
    def test_progress_callback_called(self, mock_gen, mock_close, script_task):
        mock_gen.return_value = _make_mock_script()

        _run_script_task(script_task.id)

        mock_gen.assert_called_once()
        call_kwargs = mock_gen.call_args
        # progress_callback should be passed as a keyword argument
        assert "progress_callback" in call_kwargs.kwargs
        assert callable(call_kwargs.kwargs["progress_callback"])


# ---------------------------------------------------------------------------
# TestRunNarrationTask
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestRunNarrationTask:

    @patch("apps.audio.task_runner.close_old_connections")
    @patch("apps.audio.task_runner.generate_narration")
    def test_success(self, mock_gen, mock_close, narration_task, story):
        mock_gen.return_value = _make_mock_narration_result()
        voice_map = {"Narrator": "voice_abc"}

        _run_narration_task(narration_task.id, voice_map, bust_cache=False)

        narration_task.refresh_from_db()
        story.refresh_from_db()

        assert narration_task.status == "completed"
        assert story.audio_file_path == "/tmp/test_audio.mp3"
        assert "audio_file" in narration_task.result_json

    @patch("apps.audio.task_runner.close_old_connections")
    @patch("apps.audio.task_runner.generate_narration")
    def test_failure(self, mock_gen, mock_close, narration_task):
        mock_gen.side_effect = RuntimeError("TTS service error")
        voice_map = {"Narrator": "voice_abc"}

        _run_narration_task(narration_task.id, voice_map, bust_cache=False)

        narration_task.refresh_from_db()
        assert narration_task.status == "failed"
        assert "TTS service error" in narration_task.error_message

    @patch("apps.audio.task_runner.close_old_connections")
    @patch("apps.audio.task_runner.generate_narration")
    def test_no_script(self, mock_gen, mock_close, user, db):
        no_script_story = Story.objects.create(
            title="No Script",
            text_content="Some text here.",
            content_hash="noscript_hash_789",
        )
        task = GenerationTask.objects.create(
            user=user,
            story=no_script_story,
            task_type="narration",
            status="queued",
            stage="Queued",
        )
        voice_map = {"Narrator": "voice_abc"}

        _run_narration_task(task.id, voice_map, bust_cache=False)

        task.refresh_from_db()
        assert task.status == "failed"
        assert "no script" in task.error_message.lower()
        mock_gen.assert_not_called()

    @patch("apps.audio.task_runner.close_old_connections")
    @patch("apps.audio.task_runner.generate_narration")
    def test_progress_callback_called(self, mock_gen, mock_close, narration_task):
        mock_gen.return_value = _make_mock_narration_result()
        voice_map = {"Narrator": "voice_abc"}

        _run_narration_task(narration_task.id, voice_map, bust_cache=False)

        mock_gen.assert_called_once()
        call_kwargs = mock_gen.call_args
        assert "progress_callback" in call_kwargs.kwargs
        assert callable(call_kwargs.kwargs["progress_callback"])


# ---------------------------------------------------------------------------
# TestCollectSeriesCharacters
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCollectSeriesCharacters:

    def test_returns_none_when_no_series(self, story):
        assert story.series_json is None
        result = _collect_series_characters(story)
        assert result is None

    def test_returns_none_when_no_earlier_parts(self, story):
        story.reddit_url = "https://www.reddit.com/r/nosleep/comments/xyz/part2/"
        story.series_json = [
            {
                "url": "https://www.reddit.com/r/nosleep/comments/xyz/part2/",
                "created_utc": 100,
            },
        ]
        story.save()

        result = _collect_series_characters(story)
        assert result is None

    def test_merges_characters_from_earlier_parts(self, db):
        # Create earlier story with script containing characters
        earlier_story = Story.objects.create(
            title="Part 1",
            text_content="Earlier part text.",
            content_hash="earlier_hash_001",
            reddit_url="https://www.reddit.com/r/nosleep/comments/aaa/part1/",
            script_json={
                "title": "Part 1",
                "characters": {
                    "Narrator": {"voice_profile": "deep"},
                    "Sarah": {"voice_profile": "young, scared"},
                },
                "segments": [
                    {"type": "narration", "character": "Narrator", "text": "It began."},
                ],
            },
        )

        # Create current story that is part 2 in the series
        current_story = Story.objects.create(
            title="Part 2",
            text_content="Continuation of the story.",
            content_hash="current_hash_002",
            reddit_url="https://www.reddit.com/r/nosleep/comments/bbb/part2/",
            series_json=[
                {
                    "url": "https://www.reddit.com/r/nosleep/comments/aaa/part1/",
                    "created_utc": 100,
                },
                {
                    "url": "https://www.reddit.com/r/nosleep/comments/bbb/part2/",
                    "created_utc": 200,
                },
            ],
        )

        result = _collect_series_characters(current_story)

        assert result is not None
        assert "Narrator" in result
        assert "Sarah" in result
        assert result["Narrator"]["voice_profile"] == "deep"
        assert result["Sarah"]["voice_profile"] == "young, scared"
