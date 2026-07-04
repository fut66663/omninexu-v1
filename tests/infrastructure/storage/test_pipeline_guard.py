"""Tests for PipelineGuard -- cache integrity pre/post-flight checks."""

from __future__ import annotations

from pathlib import Path

import pytest

from omninexu.infrastructure.storage.checksum import ChecksumMan
from omninexu.infrastructure.storage.pipeline_guard import PipelineGuard


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    """Simulated 10-K cache with a few filing.html files."""
    d = tmp_path / "10-K"
    (d / "AAPL" / "2024-09-28").mkdir(parents=True)
    (d / "AAPL" / "2024-09-28" / "filing.html").write_text(
        "AAPL 10-K content", encoding="utf-8"
    )
    (d / "MSFT" / "2024-06-30").mkdir(parents=True)
    (d / "MSFT" / "2024-06-30" / "filing.html").write_text(
        "MSFT 10-K content", encoding="utf-8"
    )
    return d


class TestPreFlight:
    """check_cache() scans for corrupt/empty files."""

    def test_clean_cache_returns_empty(self, cache_dir: Path) -> None:
        guard = PipelineGuard()
        bad = guard.check_cache(cache_dir)
        assert bad == []

    def test_detects_empty_file(self, tmp_path: Path) -> None:
        d = tmp_path / "10-K"
        (d / "BAD" / "2024-01-01").mkdir(parents=True)
        (d / "BAD" / "2024-01-01" / "filing.html").write_text("", encoding="utf-8")

        guard = PipelineGuard()
        bad = guard.check_cache(d)
        assert len(bad) == 1

    def test_empty_cache_dir(self, tmp_path: Path) -> None:
        d = tmp_path / "empty"
        d.mkdir()
        guard = PipelineGuard()
        bad = guard.check_cache(d)
        assert bad == []


class TestPostFlight:
    """update_manifest() generates a manifest JSON."""

    def test_generates_manifest(self, cache_dir: Path, monkeypatch) -> None:
        # Redirect quality_dir to tmp_path so we don't touch production.
        from omninexu.config import data_paths
        monkeypatch.setattr(
            type(data_paths), "quality_dir",
            property(lambda self: cache_dir.parent / "quality"),
        )
        guard = PipelineGuard()
        manifest_path = guard.update_manifest(cache_dir)
        assert manifest_path is not None
        assert manifest_path.exists()

        # Verify the manifest can be validated.
        cm = ChecksumMan()
        passed, failed, _ = cm.verify_manifest(manifest_path)
        assert passed == 2
        assert failed == 0

    def test_no_html_files_returns_none(self, tmp_path: Path) -> None:
        d = tmp_path / "empty"
        d.mkdir()
        guard = PipelineGuard()
        result = guard.update_manifest(d)
        assert result is None
