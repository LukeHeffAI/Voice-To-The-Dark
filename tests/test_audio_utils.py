"""Unit tests for app.services.audio_utils."""

import os
import time
from unittest.mock import patch, MagicMock, call

import pytest

from app.services.audio_utils import (
    create_tmp_folder,
    cleanup_temp_files,
    purge_temp_folder,
    stitch_audio_files,
)


# ---------------------------------------------------------------------------
# create_tmp_folder
# ---------------------------------------------------------------------------

class TestCreateTmpFolder:
    def test_creates_folder_when_missing(self, tmp_path, monkeypatch):
        """Folder is created when it does not already exist."""
        monkeypatch.chdir(tmp_path)
        expected = os.path.join(str(tmp_path), "tmp")

        result = create_tmp_folder()

        assert result == expected
        assert os.path.isdir(expected)

    def test_returns_path_when_folder_already_exists(self, tmp_path, monkeypatch):
        """Existing folder is left intact and its path is returned."""
        monkeypatch.chdir(tmp_path)
        expected = os.path.join(str(tmp_path), "tmp")
        os.makedirs(expected)

        # Place a sentinel file to prove the folder is not recreated
        sentinel = os.path.join(expected, "sentinel.txt")
        with open(sentinel, "w") as f:
            f.write("keep me")

        result = create_tmp_folder()

        assert result == expected
        assert os.path.isdir(expected)
        assert os.path.isfile(sentinel), "Existing contents should be preserved"

    def test_return_value_is_absolute_path(self, tmp_path, monkeypatch):
        """The returned path is always absolute."""
        monkeypatch.chdir(tmp_path)

        result = create_tmp_folder()

        assert os.path.isabs(result)

    def test_nested_tmp_path_inside_cwd(self, tmp_path, monkeypatch):
        """The tmp folder is a direct child of the current working directory."""
        monkeypatch.chdir(tmp_path)

        result = create_tmp_folder()

        assert os.path.dirname(result) == str(tmp_path)
        assert os.path.basename(result) == "tmp"


# ---------------------------------------------------------------------------
# cleanup_temp_files
# ---------------------------------------------------------------------------

class TestCleanupTempFiles:
    def _make_old_file(self, folder, name, age_days):
        """Create a file and backdate its modification time."""
        path = os.path.join(str(folder), name)
        with open(path, "w") as f:
            f.write("data")
        old_time = time.time() - (age_days * 86400) - 60  # extra minute for safety
        os.utime(path, (old_time, old_time))
        return path

    def _make_recent_file(self, folder, name):
        """Create a file with the current modification time."""
        path = os.path.join(str(folder), name)
        with open(path, "w") as f:
            f.write("data")
        return path

    def test_old_files_are_removed(self, tmp_path):
        """Files older than the threshold are deleted."""
        old_file = self._make_old_file(tmp_path, "old.mp3", age_days=10)

        cleanup_temp_files(folder=str(tmp_path), days=7)

        assert not os.path.exists(old_file)

    def test_recent_files_are_kept(self, tmp_path):
        """Files newer than the threshold are kept."""
        recent_file = self._make_recent_file(tmp_path, "recent.mp3")

        cleanup_temp_files(folder=str(tmp_path), days=7)

        assert os.path.exists(recent_file)

    def test_mixed_old_and_recent(self, tmp_path):
        """Only old files are removed; recent ones survive."""
        old_file = self._make_old_file(tmp_path, "old.mp3", age_days=10)
        recent_file = self._make_recent_file(tmp_path, "recent.mp3")

        cleanup_temp_files(folder=str(tmp_path), days=7)

        assert not os.path.exists(old_file)
        assert os.path.exists(recent_file)

    def test_nonexistent_folder_is_noop(self):
        """Calling with a folder that doesn't exist does nothing (no exception)."""
        cleanup_temp_files(folder="/tmp/nonexistent_folder_that_does_not_exist", days=1)

    def test_custom_days_threshold(self, tmp_path):
        """A custom `days` value is respected."""
        # File is 3 days old — should be removed when threshold is 2 days
        file_3d = self._make_old_file(tmp_path, "three_day.mp3", age_days=3)

        cleanup_temp_files(folder=str(tmp_path), days=2)

        assert not os.path.exists(file_3d)

    def test_custom_days_threshold_keeps_newer(self, tmp_path):
        """A file within the custom threshold is kept."""
        # File is 1 day old — should survive a 2-day threshold
        file_1d = self._make_old_file(tmp_path, "one_day.mp3", age_days=1)

        cleanup_temp_files(folder=str(tmp_path), days=2)

        assert os.path.exists(file_1d)

    def test_subdirectories_are_not_deleted(self, tmp_path):
        """Only regular files are considered; subdirectories are ignored."""
        subdir = os.path.join(str(tmp_path), "subdir")
        os.makedirs(subdir)
        # Backdate the subdir so it would be "old"
        old_time = time.time() - (30 * 86400)
        os.utime(subdir, (old_time, old_time))

        cleanup_temp_files(folder=str(tmp_path), days=7)

        assert os.path.isdir(subdir), "Subdirectories should not be removed"

    def test_defaults_to_cwd_tmp(self, tmp_path, monkeypatch):
        """When no folder is given, defaults to <cwd>/tmp."""
        monkeypatch.chdir(tmp_path)
        default_folder = os.path.join(str(tmp_path), "tmp")
        os.makedirs(default_folder)
        old_file = self._make_old_file(default_folder, "old.mp3", age_days=10)

        cleanup_temp_files(days=7)

        assert not os.path.exists(old_file)

    def test_empty_folder_is_noop(self, tmp_path):
        """An existing but empty folder causes no errors."""
        cleanup_temp_files(folder=str(tmp_path), days=7)

    def test_unremovable_file_logs_warning(self, tmp_path):
        """A file that can't be removed is logged as a warning, not raised."""
        old_file = self._make_old_file(tmp_path, "locked.mp3", age_days=10)

        with patch("app.services.audio_utils.os.remove", side_effect=PermissionError("denied")):
            with patch("app.services.audio_utils.logging") as mock_logging:
                cleanup_temp_files(folder=str(tmp_path), days=7)
                mock_logging.warning.assert_called_once()


# ---------------------------------------------------------------------------
# purge_temp_folder
# ---------------------------------------------------------------------------

class TestPurgeTempFolder:
    def test_folder_is_removed_and_recreated_empty(self, tmp_path, monkeypatch):
        """After purge, the folder exists but is empty."""
        monkeypatch.chdir(tmp_path)
        target = os.path.join(str(tmp_path), "tmp")
        os.makedirs(target)
        # Add some files
        for name in ("a.mp3", "b.mp3", "c.txt"):
            with open(os.path.join(target, name), "w") as f:
                f.write("data")

        purge_temp_folder(folder=target)

        assert os.path.isdir(target), "Folder should be recreated"
        assert os.listdir(target) == [], "Folder should be empty after purge"

    def test_nonexistent_folder_handled_gracefully(self, tmp_path, monkeypatch):
        """Purging a non-existent folder does not raise."""
        monkeypatch.chdir(tmp_path)
        missing = os.path.join(str(tmp_path), "tmp")
        assert not os.path.exists(missing)

        # Should not raise — shutil.rmtree will fail but exception is caught,
        # then create_tmp_folder will create it.
        purge_temp_folder(folder=missing)

    def test_defaults_to_cwd_tmp(self, tmp_path, monkeypatch):
        """When no folder is given, defaults to <cwd>/tmp."""
        monkeypatch.chdir(tmp_path)
        default_folder = os.path.join(str(tmp_path), "tmp")
        os.makedirs(default_folder)
        sentinel = os.path.join(default_folder, "sentinel.txt")
        with open(sentinel, "w") as f:
            f.write("data")

        purge_temp_folder()

        assert os.path.isdir(default_folder)
        assert not os.path.exists(sentinel), "Old contents should be gone"

    def test_logs_info_on_success(self, tmp_path, monkeypatch):
        """A successful purge logs an info message."""
        monkeypatch.chdir(tmp_path)
        target = os.path.join(str(tmp_path), "tmp")
        os.makedirs(target)

        with patch("app.services.audio_utils.logging") as mock_logging:
            purge_temp_folder(folder=target)
            mock_logging.info.assert_called_once()

    def test_logs_warning_on_rmtree_failure(self, tmp_path, monkeypatch):
        """If rmtree fails, a warning is logged."""
        monkeypatch.chdir(tmp_path)
        target = os.path.join(str(tmp_path), "tmp")

        with patch("app.services.audio_utils.shutil.rmtree", side_effect=OSError("boom")):
            with patch("app.services.audio_utils.logging") as mock_logging:
                purge_temp_folder(folder=target)
                mock_logging.warning.assert_called_once()

    def test_folder_recreated_even_after_rmtree_failure(self, tmp_path, monkeypatch):
        """create_tmp_folder is called in the finally block even if rmtree fails."""
        monkeypatch.chdir(tmp_path)
        target = os.path.join(str(tmp_path), "tmp")

        with patch("app.services.audio_utils.shutil.rmtree", side_effect=OSError("boom")):
            purge_temp_folder(folder=target)

        # create_tmp_folder uses os.getcwd()/tmp, so it should exist
        expected_recreated = os.path.join(str(tmp_path), "tmp")
        assert os.path.isdir(expected_recreated)


# ---------------------------------------------------------------------------
# stitch_audio_files
# ---------------------------------------------------------------------------

class TestStitchAudioFiles:
    def test_empty_list_returns_none(self):
        """An empty file list is a no-op, returning None."""
        result = stitch_audio_files([], "/fake/output.mp3")

        assert result is None

    @patch("app.services.audio_utils.AudioSegment")
    def test_single_file(self, mock_audio_cls):
        """A single file is loaded and exported without concatenation."""
        mock_segment = MagicMock(name="segment_0")
        mock_audio_cls.from_file.return_value = mock_segment

        stitch_audio_files(["/tmp/chunk_0.mp3"], "/tmp/output.mp3")

        mock_audio_cls.from_file.assert_called_once_with("/tmp/chunk_0.mp3", format="mp3")
        mock_segment.export.assert_called_once_with("/tmp/output.mp3", format="mp3")

    @patch("app.services.audio_utils.AudioSegment")
    def test_multiple_files_concatenated(self, mock_audio_cls):
        """Multiple files are loaded in order and concatenated via +=."""
        seg_a = MagicMock(name="segment_a")
        seg_b = MagicMock(name="segment_b")
        seg_c = MagicMock(name="segment_c")

        # combined starts as seg_a, then += returns a new combined segment each time
        combined_ab = MagicMock(name="combined_ab")
        combined_abc = MagicMock(name="combined_abc")
        seg_a.__iadd__ = MagicMock(return_value=combined_ab)
        combined_ab.__iadd__ = MagicMock(return_value=combined_abc)

        mock_audio_cls.from_file.side_effect = [seg_a, seg_b, seg_c]

        stitch_audio_files(
            ["/tmp/a.mp3", "/tmp/b.mp3", "/tmp/c.mp3"],
            "/tmp/output.mp3",
        )

        assert mock_audio_cls.from_file.call_count == 3
        mock_audio_cls.from_file.assert_any_call("/tmp/a.mp3", format="mp3")
        mock_audio_cls.from_file.assert_any_call("/tmp/b.mp3", format="mp3")
        mock_audio_cls.from_file.assert_any_call("/tmp/c.mp3", format="mp3")

        # seg_a += seg_b
        seg_a.__iadd__.assert_called_once_with(seg_b)
        # combined_ab += seg_c
        combined_ab.__iadd__.assert_called_once_with(seg_c)

        # Final combined result is exported
        combined_abc.export.assert_called_once_with("/tmp/output.mp3", format="mp3")

    @patch("app.services.audio_utils.AudioSegment")
    def test_two_files_concatenated(self, mock_audio_cls):
        """Verify the simplest multi-file case (two files)."""
        seg_first = MagicMock(name="first")
        seg_second = MagicMock(name="second")
        combined = MagicMock(name="combined")
        seg_first.__iadd__ = MagicMock(return_value=combined)

        mock_audio_cls.from_file.side_effect = [seg_first, seg_second]

        stitch_audio_files(["/tmp/1.mp3", "/tmp/2.mp3"], "/tmp/out.mp3")

        seg_first.__iadd__.assert_called_once_with(seg_second)
        combined.export.assert_called_once_with("/tmp/out.mp3", format="mp3")

    @patch("app.services.audio_utils.AudioSegment")
    def test_export_uses_mp3_format(self, mock_audio_cls):
        """The export always specifies format='mp3'."""
        mock_segment = MagicMock()
        mock_audio_cls.from_file.return_value = mock_segment

        stitch_audio_files(["/tmp/only.mp3"], "/tmp/result.mp3")

        _, kwargs = mock_segment.export.call_args
        assert kwargs["format"] == "mp3"

    @patch("app.services.audio_utils.AudioSegment")
    def test_from_file_called_with_mp3_format(self, mock_audio_cls):
        """Each from_file call specifies format='mp3'."""
        mock_audio_cls.from_file.return_value = MagicMock()

        stitch_audio_files(["/tmp/x.mp3", "/tmp/y.mp3"], "/tmp/out.mp3")

        for c in mock_audio_cls.from_file.call_args_list:
            assert c == call(c[0][0], format="mp3")

    def test_none_input_returns_none(self):
        """Passing None as file_paths (falsy) also returns early."""
        # The function checks `if not file_paths:` which is True for None
        result = stitch_audio_files(None, "/tmp/output.mp3")

        assert result is None

    @patch("app.services.audio_utils.AudioSegment")
    def test_files_loaded_in_order(self, mock_audio_cls):
        """Files are loaded in the exact order they appear in the list."""
        mock_audio_cls.from_file.return_value = MagicMock()

        paths = ["/tmp/01.mp3", "/tmp/02.mp3", "/tmp/03.mp3", "/tmp/04.mp3"]
        stitch_audio_files(paths, "/tmp/out.mp3")

        loaded_paths = [c[0][0] for c in mock_audio_cls.from_file.call_args_list]
        assert loaded_paths == paths
