"""Tests for DiskValidator — file existence, directory counts, anomaly scans.

Covers the core validate_file / validate_directory / validate_tree /
find_empty_files / find_stale_files API.  Disk-space tests are in
test_disk_validator_coverage.py.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from omninexu.infrastructure.storage.disk_validator import DiskValidator

# ═══════════════════════════════════════════════════════════════
# validate_file()
# ═══════════════════════════════════════════════════════════════


class TestValidateFile:
    """Single-file existence and size checks."""

    def test_existing_nonempty_file_returns_true(self, tmp_path: Path) -> None:
        f = tmp_path / "a.txt"
        f.write_text("hello", encoding="utf-8")
        assert DiskValidator.validate_file(f) is True

    def test_missing_file_returns_false(self, tmp_path: Path) -> None:
        assert DiskValidator.validate_file(tmp_path / "missing.txt") is False

    def test_empty_file_with_default_min_bytes_returns_false(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")
        assert DiskValidator.validate_file(f) is False

    def test_empty_file_with_min_bytes_zero_returns_true(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")
        assert DiskValidator.validate_file(f, min_bytes=0) is True

    def test_file_below_min_bytes_returns_false(self, tmp_path: Path) -> None:
        f = tmp_path / "tiny.txt"
        f.write_text("ab", encoding="utf-8")
        assert DiskValidator.validate_file(f, min_bytes=100) is False

    def test_path_is_directory_returns_false(self, tmp_path: Path) -> None:
        d = tmp_path / "subdir"
        d.mkdir()
        assert DiskValidator.validate_file(d) is False


# ═══════════════════════════════════════════════════════════════
# validate_directory()
# ═══════════════════════════════════════════════════════════════


class TestValidateDirectory:
    """Directory-level file counting."""

    def test_counts_files_recursively(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("a", encoding="utf-8")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "b.txt").write_text("b", encoding="utf-8")

        count, _, _ = DiskValidator.validate_directory(tmp_path)
        assert count == 2

    def test_glob_filters_by_extension(self, tmp_path: Path) -> None:
        (tmp_path / "filing.html").write_text("html", encoding="utf-8")
        (tmp_path / "notes.txt").write_text("txt", encoding="utf-8")

        count, _, _ = DiskValidator.validate_directory(tmp_path, glob="*.html")
        assert count == 1

    def test_min_files_not_met(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("a", encoding="utf-8")
        count, expected, _ = DiskValidator.validate_directory(tmp_path, min_files=10)
        assert count == 1
        assert expected == 10

    def test_min_files_met(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("a", encoding="utf-8")
        count, _, missing = DiskValidator.validate_directory(tmp_path, min_files=1)
        assert count == 1
        assert missing == []

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        count, expected, missing = DiskValidator.validate_directory(
            tmp_path / "no_dir", min_files=5
        )
        assert count == 0
        assert expected == 5
        assert len(missing) == 1


# ═══════════════════════════════════════════════════════════════
# validate_tree()
# ═══════════════════════════════════════════════════════════════


class TestValidateTree:
    """Multi-subdirectory structure validation."""

    def test_returns_actual_counts_for_each_key(self, tmp_path: Path) -> None:
        (tmp_path / "10-K").mkdir()
        (tmp_path / "10-K" / "f1.html").write_text("f1", encoding="utf-8")
        (tmp_path / "10-K" / "f2.html").write_text("f2", encoding="utf-8")
        (tmp_path / "13F").mkdir()
        (tmp_path / "13F" / "f3.html").write_text("f3", encoding="utf-8")

        actual = DiskValidator.validate_tree(
            tmp_path, {"10-K": 2, "13F": 1, "Form-4": 0}
        )
        assert actual == {"10-K": 2, "13F": 1, "Form-4": 0}

    def test_missing_subdir_counts_as_zero(self, tmp_path: Path) -> None:
        actual = DiskValidator.validate_tree(tmp_path, {"10-K": 1})
        assert actual == {"10-K": 0}


# ═══════════════════════════════════════════════════════════════
# find_empty_files()
# ═══════════════════════════════════════════════════════════════


class TestFindEmptyFiles:
    """Zero-byte file detection."""

    def test_finds_empty_files(self, tmp_path: Path) -> None:
        (tmp_path / "good.txt").write_text("content", encoding="utf-8")
        (tmp_path / "empty.txt").write_text("", encoding="utf-8")
        (tmp_path / "also_empty.html").write_text("", encoding="utf-8")

        empties = DiskValidator.find_empty_files(tmp_path)
        names = {p.name for p in empties}
        assert names == {"empty.txt", "also_empty.html"}

    def test_no_empty_files_returns_empty_list(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("content", encoding="utf-8")
        assert DiskValidator.find_empty_files(tmp_path) == []

    def test_nonexistent_directory_returns_empty(self, tmp_path: Path) -> None:
        assert DiskValidator.find_empty_files(tmp_path / "no_dir") == []

    def test_directories_not_counted(self, tmp_path: Path) -> None:
        (tmp_path / "empty_dir").mkdir()
        assert DiskValidator.find_empty_files(tmp_path) == []


# ═══════════════════════════════════════════════════════════════
# find_stale_files()
# ═══════════════════════════════════════════════════════════════


class TestFindStaleFiles:
    """Stale file detection based on modification time."""

    def test_finds_stale_files(self, tmp_path: Path) -> None:
        f = tmp_path / "old.txt"
        f.write_text("old", encoding="utf-8")
        # Set mtime to 60 days ago.
        old_time = time.time() - (60 * 86400)
        os.utime(f, (old_time, old_time))

        stale = DiskValidator.find_stale_files(tmp_path, max_age_days=30)
        assert f in stale

    def test_fresh_file_not_flagged(self, tmp_path: Path) -> None:
        f = tmp_path / "new.txt"
        f.write_text("new", encoding="utf-8")

        stale = DiskValidator.find_stale_files(tmp_path, max_age_days=30)
        assert f not in stale

    def test_nonexistent_directory_returns_empty(self, tmp_path: Path) -> None:
        assert DiskValidator.find_stale_files(tmp_path / "no_dir") == []


