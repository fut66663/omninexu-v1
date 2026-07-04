"""Disk-space and size-coverage tests for DiskValidator.

Core file/directory validation tests are in test_disk_validator.py.
"""

from __future__ import annotations

from pathlib import Path

from omninexu.infrastructure.storage.disk_validator import DiskValidator

# ═══════════════════════════════════════════════════════════════
# get_directory_size()
# ═══════════════════════════════════════════════════════════════


class TestGetDirectorySize:
    """Recursive directory size calculation."""

    def test_sums_file_sizes(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("hello", encoding="utf-8")  # 5 bytes
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "b.txt").write_text("world!", encoding="utf-8")  # 6 bytes

        size = DiskValidator.get_directory_size(tmp_path)
        assert size == 11

    def test_empty_directory_returns_zero(self, tmp_path: Path) -> None:
        assert DiskValidator.get_directory_size(tmp_path) == 0

    def test_nonexistent_returns_zero(self, tmp_path: Path) -> None:
        assert DiskValidator.get_directory_size(tmp_path / "no_dir") == 0

    def test_nested_empty_subdirs(self, tmp_path: Path) -> None:
        (tmp_path / "a" / "b" / "c").mkdir(parents=True)
        (tmp_path / "a" / "data.txt").write_text("x", encoding="utf-8")
        size = DiskValidator.get_directory_size(tmp_path)
        assert size == 1


# ═══════════════════════════════════════════════════════════════
# check_space()
# ═══════════════════════════════════════════════════════════════


class TestCheckSpace:
    """Free-space checks against a volume."""

    def test_trivially_small_request_passes(self, tmp_path: Path) -> None:
        """Asking for 1 byte on a non-full volume should pass."""
        assert DiskValidator.check_space(1, tmp_path) is True

    def test_absurdly_large_request_fails(self, tmp_path: Path) -> None:
        """Asking for 1 PiB should fail on any reasonable machine."""
        one_pib = 1 * 1024**5
        assert DiskValidator.check_space(one_pib, tmp_path) is False

    def test_oserror_graceful_fallback(self, tmp_path: Path) -> None:
        """Nonexistent path yields False, not an exception."""
        assert DiskValidator.check_space(1, tmp_path / "no_such_volume") is False


# ═══════════════════════════════════════════════════════════════
# get_growth_trend()
# ═══════════════════════════════════════════════════════════════


class TestGetGrowthTrend:
    """Per-day size aggregation."""

    def test_returns_list_of_date_size_entries(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("hello", encoding="utf-8")

        trend = DiskValidator.get_growth_trend(tmp_path, days=7)
        assert isinstance(trend, list)
        if trend:
            entry = trend[0]
            assert "date" in entry
            assert "size_bytes" in entry

    def test_empty_directory_returns_empty(self, tmp_path: Path) -> None:
        assert DiskValidator.get_growth_trend(tmp_path, days=7) == []

    def test_nonexistent_returns_empty(self, tmp_path: Path) -> None:
        assert DiskValidator.get_growth_trend(tmp_path / "no_dir") == []

    def test_respects_days_window(self, tmp_path: Path) -> None:
        """Only files modified within the window should be counted."""
        (tmp_path / "fresh.txt").write_text("hello", encoding="utf-8")
        trend = DiskValidator.get_growth_trend(tmp_path, days=365)
        # At least one entry for the fresh file.
        assert len(trend) >= 1
        total = sum(e["size_bytes"] for e in trend)
        assert total == 5


# ═══════════════════════════════════════════════════════════════
# find_suspect_directories()
# ═══════════════════════════════════════════════════════════════


class TestFindSuspectDirectories:
    """Suspicious / non-ticker directory detection."""

    def test_flags_magicmock(self, tmp_path: Path) -> None:
        (tmp_path / "AAPL").mkdir()
        (tmp_path / "AAPL" / "filing.html").write_text("data", encoding="utf-8")
        (tmp_path / "MagicMock").mkdir()
        suspects = DiskValidator.find_suspect_directories(tmp_path)
        names = {p.name for p in suspects}
        assert "MagicMock" in names
        assert "AAPL" not in names

    def test_flags_empty_directory(self, tmp_path: Path) -> None:
        (tmp_path / "EMPTY").mkdir()
        suspects = DiskValidator.find_suspect_directories(tmp_path)
        assert len(suspects) >= 1

    def test_flags_lowercase_name(self, tmp_path: Path) -> None:
        (tmp_path / "data").mkdir()
        suspects = DiskValidator.find_suspect_directories(tmp_path)
        assert len(suspects) >= 1

    def test_ticker_dirs_are_not_suspect(self, tmp_path: Path) -> None:
        for t in ("AAPL", "MSFT", "GOOGL"):
            (tmp_path / t).mkdir()
            # Put a file in so they're not empty.
            (tmp_path / t / "filing.html").write_text("data", encoding="utf-8")
        suspects = DiskValidator.find_suspect_directories(tmp_path)
        assert len(suspects) == 0

    def test_nonexistent_directory_returns_empty(self, tmp_path: Path) -> None:
        assert DiskValidator.find_suspect_directories(tmp_path / "no_dir") == []
