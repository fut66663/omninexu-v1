"""Tests for scripts/ops/rotate_logs.py."""

from datetime import date, timedelta
from unittest.mock import patch


class TestRotate:
    def test_rotate_returns_empty_when_no_log_dir(self, tmp_path):
        """rotate() returns [] when log directory doesn't exist."""
        from scripts.ops.rotate_logs import rotate

        nonexistent = tmp_path / "nonexistent"

        with patch("scripts.ops.rotate_logs.data_paths") as mock_paths:
            mock_paths.logs_api = nonexistent
            result = rotate()
            assert result == []

    def test_rotate_deletes_old_logs(self, tmp_path):
        """rotate() deletes log files older than 90 days."""
        from scripts.ops.rotate_logs import rotate

        # Create old and recent log files
        old_month = (date.today().replace(day=1) - timedelta(days=120))
        recent_month = date.today().replace(day=1)
        (tmp_path / f"{old_month.strftime('%Y-%m')}.jsonl").write_text("old log")
        (tmp_path / f"{recent_month.strftime('%Y-%m')}.jsonl").write_text("recent log")

        with patch("scripts.ops.rotate_logs.data_paths") as mock_paths:
            mock_paths.logs_api = tmp_path
            result = rotate(dry_run=False)

            assert len(result) == 1
            assert not (tmp_path / f"{old_month.strftime('%Y-%m')}.jsonl").exists()
            assert (tmp_path / f"{recent_month.strftime('%Y-%m')}.jsonl").exists()

    def test_rotate_dry_run_does_not_delete(self, tmp_path):
        """dry_run=True should list but not delete files."""
        from scripts.ops.rotate_logs import rotate

        old_month = (date.today().replace(day=1) - timedelta(days=120))
        fp = tmp_path / f"{old_month.strftime('%Y-%m')}.jsonl"
        fp.write_text("old log")

        with patch("scripts.ops.rotate_logs.data_paths") as mock_paths:
            mock_paths.logs_api = tmp_path
            result = rotate(dry_run=True)

            assert len(result) == 1
            assert fp.exists()  # not deleted

    def test_rotate_skips_invalid_filenames(self, tmp_path):
        """rotate() skips files that don't match YYYY-MM.jsonl pattern."""
        from scripts.ops.rotate_logs import rotate

        (tmp_path / "not-a-log.txt").write_text("junk")
        (tmp_path / "also_invalid.jsonl").write_text("bad format")

        with patch("scripts.ops.rotate_logs.data_paths") as mock_paths:
            mock_paths.logs_api = tmp_path
            result = rotate()
            assert result == []  # no valid log files to delete
            assert (tmp_path / "not-a-log.txt").exists()
