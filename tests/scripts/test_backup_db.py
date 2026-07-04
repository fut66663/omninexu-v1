"""Tests for scripts/ops/backup_db.py."""

from datetime import date, timedelta
from unittest.mock import patch


class TestBackup:
    def test_backup_succeeds(self, tmp_path):
        """backup() runs pg_dump and returns the output path."""
        from scripts.ops.backup_db import backup

        with (
            patch("scripts.ops.backup_db.subprocess.run") as mock_run,
            patch("scripts.ops.backup_db.data_paths") as mock_paths,
        ):
            mock_paths.backup_dir = tmp_path
            mock_run.return_value.returncode = 0

            result = backup()
            assert result is not None
            assert result.suffix == ".dump"

    def test_backup_returns_none_on_failure(self, tmp_path):
        """backup() returns None when pg_dump fails."""
        from scripts.ops.backup_db import backup

        with (
            patch("scripts.ops.backup_db.subprocess.run") as mock_run,
            patch("scripts.ops.backup_db.data_paths") as mock_paths,
        ):
            mock_paths.backup_dir = tmp_path
            mock_run.return_value.returncode = 1
            mock_run.return_value.stderr = "connection refused"

            result = backup()
            assert result is None

    def test_backup_removes_old_files(self, tmp_path):
        """backup() should remove backups older than keep_days."""
        from scripts.ops.backup_db import backup

        # Create some old backup files
        old_date = (date.today() - timedelta(days=60)).isoformat()
        recent_date = (date.today() - timedelta(days=5)).isoformat()
        (tmp_path / f"omninexu_{old_date}.dump").write_text("old")
        (tmp_path / f"omninexu_{recent_date}.dump").write_text("recent")

        with (
            patch("scripts.ops.backup_db.subprocess.run") as mock_run,
            patch("scripts.ops.backup_db.data_paths") as mock_paths,
        ):
            mock_paths.backup_dir = tmp_path
            mock_run.return_value.returncode = 0

            backup(keep_days=30)

            # Old file should be removed
            assert not (tmp_path / f"omninexu_{old_date}.dump").exists()
            # Recent file should remain
            assert (tmp_path / f"omninexu_{recent_date}.dump").exists()

    def test_backup_skips_non_matching_files(self, tmp_path):
        """Non-backup files in backup dir should be ignored."""
        from scripts.ops.backup_db import backup

        (tmp_path / "readme.txt").write_text("info")
        (tmp_path / f"omninexu_{date.today().isoformat()}.dump").touch()

        with (
            patch("scripts.ops.backup_db.subprocess.run") as mock_run,
            patch("scripts.ops.backup_db.data_paths") as mock_paths,
        ):
            mock_paths.backup_dir = tmp_path
            mock_run.return_value.returncode = 0

            result = backup(keep_days=30)
            assert result is not None
            # readme.txt should still exist
            assert (tmp_path / "readme.txt").exists()
