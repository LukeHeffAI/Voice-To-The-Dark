"""Tests for background task functions."""

from unittest.mock import MagicMock, patch

import pytest

from apps.audio.helpers import pydantic_to_script
from apps.tasks.models import BackgroundTask, TaskStatus, TaskType
from apps.tasks.task_functions import run_generate_narration, run_generate_script
from schemas.narration import CharacterProfile, NarrationScript, ScriptSegment, SegmentType


pytestmark = pytest.mark.django_db


@pytest.fixture
def script_task(test_user, test_story):
    """Create a background task for script generation."""
    return BackgroundTask.objects.create(
        user=test_user,
        story=test_story,
        task_type=TaskType.GENERATE_SCRIPT,
        status=TaskStatus.PROCESSING,
    )


@pytest.fixture
def narration_task(test_user, test_story):
    """Create a background task for narration generation."""
    return BackgroundTask.objects.create(
        user=test_user,
        story=test_story,
        task_type=TaskType.GENERATE_NARRATION,
        status=TaskStatus.PROCESSING,
    )


@pytest.fixture
def story_with_script(test_story):
    """Create a story with a script for narration tests."""
    script = NarrationScript(
        title="Test Script",
        characters={
            "Narrator": CharacterProfile(voice_profile="deep, steady"),
        },
        segments=[
            ScriptSegment(type=SegmentType.NARRATION, character="Narrator", text="It was dark.", tone="ominous"),
        ],
    )
    pydantic_to_script(test_story, script)
    return test_story


class TestRunGenerateScript:
    @patch("services.script_adapter.generate_script")
    def test_success(self, mock_gen, script_task, test_story):
        mock_script = NarrationScript(
            title="Generated Script",
            characters={"Narrator": CharacterProfile(voice_profile="deep")},
            segments=[ScriptSegment(type=SegmentType.NARRATION, character="Narrator", text="Hello.")],
        )
        mock_gen.return_value = mock_script

        result = run_generate_script(script_task, test_story.id)

        assert result["message"] == "Script generated successfully!"
        assert "Narrator" in result["characters"]
        mock_gen.assert_called_once()

        # Verify progress was updated
        script_task.refresh_from_db()
        assert script_task.progress_message == "Saving script..."

    @patch("services.script_adapter.generate_script")
    def test_with_prior_characters(self, mock_gen, script_task, test_story):
        mock_script = NarrationScript(
            title="Part 2",
            characters={"Narrator": CharacterProfile(voice_profile="deep")},
            segments=[ScriptSegment(type=SegmentType.NARRATION, character="Narrator", text="Hello.")],
        )
        mock_gen.return_value = mock_script

        prior = {"OldChar": {"voice_profile": "raspy"}}
        result = run_generate_script(script_task, test_story.id, prior_characters=prior)

        assert result["message"] == "Script generated successfully!"
        mock_gen.assert_called_once_with(
            test_story.title,
            test_story.narration_text,
            prior_characters=prior,
        )


class TestRunGenerateNarration:
    @patch("services.narration_generator.generate_narration")
    def test_success(self, mock_gen, narration_task, story_with_script):
        mock_result = MagicMock()
        mock_result.output_path = "/data/stories/narrated.mp3"
        mock_result.total_segments = 1
        mock_result.cache_hits = 0
        mock_result.cache_misses = 1
        mock_gen.return_value = mock_result

        script = NarrationScript(
            title="Test Script",
            characters={"Narrator": CharacterProfile(voice_profile="deep")},
            segments=[ScriptSegment(type=SegmentType.NARRATION, character="Narrator", text="It was dark.")],
        )
        voice_map = {"Narrator": "v1"}

        result = run_generate_narration(
            narration_task, story_with_script.id, voice_map, script.model_dump()
        )

        assert result["message"] == "Narration generated successfully!"
        assert result["audio_file"] == "/data/stories/narrated.mp3"
        assert result["cache_stats"]["total_segments"] == 1

        # Verify story was updated
        story_with_script.refresh_from_db()
        assert story_with_script.audio_file_path == "/data/stories/narrated.mp3"

        # Verify progress was updated
        narration_task.refresh_from_db()
        assert narration_task.status == TaskStatus.MIXING

    @patch("services.narration_generator.generate_narration")
    def test_progress_callback_called(self, mock_gen, narration_task, story_with_script):
        """Verify the progress callback is passed to generate_narration."""
        mock_result = MagicMock()
        mock_result.output_path = "/data/stories/test.mp3"
        mock_result.total_segments = 1
        mock_result.cache_hits = 0
        mock_result.cache_misses = 1
        mock_gen.return_value = mock_result

        script = NarrationScript(
            title="Test Script",
            characters={"Narrator": CharacterProfile(voice_profile="deep")},
            segments=[ScriptSegment(type=SegmentType.NARRATION, character="Narrator", text="Hello.")],
        )

        run_generate_narration(narration_task, story_with_script.id, {"Narrator": "v1"}, script.model_dump())

        # Verify generate_narration was called with a progress_callback
        call_kwargs = mock_gen.call_args
        assert call_kwargs.kwargs.get("progress_callback") is not None
