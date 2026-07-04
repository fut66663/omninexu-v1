"""Integration test: PipelineGuard + PipelineHook in a simulated pipeline run.

Simulates the exact pattern ingest scripts will use — no mocks, real files.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from omninexu.infrastructure.storage import PipelineGuard, PipelineHook


@pytest.fixture
def simulated_cache(tmp_path: Path) -> Path:
    """Simulated 10-K cache with 3 tickers."""
    cache = tmp_path / "10-K"
    for t, date_str in [("AAPL", "2024-09-28"), ("MSFT", "2024-06-30"),
                          ("GOOGL", "2024-12-31")]:
        d = cache / t / date_str
        d.mkdir(parents=True)
        (d / "filing.html").write_text(f"{t} 10-K filing content\n", encoding="utf-8")
    return cache


@pytest.fixture
def log_dir(tmp_path: Path) -> Path:
    d = tmp_path / "logs"
    d.mkdir()
    return d


class TestGuardThenHookPipeline:
    """Simulate: guard pre-flight → hook steps → guard post-flight."""

    def test_full_simulated_run(
        self, simulated_cache: Path, log_dir: Path, monkeypatch
    ) -> None:
        # -- Redirect quality_dir so manifest doesn't touch production --
        quality = simulated_cache.parent / "quality"
        quality.mkdir()
        from omninexu.config import data_paths
        monkeypatch.setattr(
            type(data_paths), "quality_dir",
            property(lambda self, q=quality: q),
        )

        # ================================================================
        # Step 1: Pre-flight — guard checks cache integrity
        # ================================================================
        guard = PipelineGuard()
        corrupt = guard.check_cache(simulated_cache)
        assert corrupt == [], f"Clean cache should have no corrupt files, got {corrupt}"

        # ================================================================
        # Step 2: Simulate a pipeline run with hook recording each step
        # ================================================================
        hook = PipelineHook(log_dir)
        tickers = ["AAPL", "MSFT", "GOOGL"]

        for ticker in tickers:
            # -- download step --
            hook.record("download", ticker, ok=True, bytes_written=50000)
            # -- parse step --
            hook.record("parse", ticker, ok=True, facts_extracted=45)
            # -- save step --
            hook.record("save", ticker, ok=True, rows_inserted=45)

        # Simulate one failure.
        hook.record("download", "BROKEN", ok=False, error="SEC rate limit")

        hook.log_summary()

        # ================================================================
        # Step 3: Verify the JSONL log file
        # ================================================================
        log_files = list(log_dir.rglob("*.jsonl"))
        assert len(log_files) == 1, f"Expected 1 log file, got {len(log_files)}"
        lines = log_files[0].read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 10, f"Expected 10 log entries, got {len(lines)}"

        steps = [json.loads(line)["step"] for line in lines]
        assert steps.count("download") == 4  # 3 ok + 1 failed
        assert steps.count("parse") == 3
        assert steps.count("save") == 3

        # Verify all entries have a run_id.
        run_ids = {json.loads(line)["run_id"] for line in lines}
        assert len(run_ids) == 1, "All entries should share the same run_id"

        # Verify failed entry has status "failed".
        failed = [json.loads(line) for line in lines
                  if json.loads(line).get("status") == "failed"]
        assert len(failed) == 1
        assert failed[0]["ticker"] == "BROKEN"

        # ================================================================
        # Step 4: Post-flight — guard updates manifest
        # ================================================================
        manifest = guard.update_manifest(simulated_cache)
        assert manifest is not None
        assert manifest.exists()

        # Verify manifest covers all 3 filing.html files.
        manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
        assert len(manifest_data["files"]) == 3


class TestGuardDetectsCorruption:
    """PipelineGuard must detect real file corruption."""

    def test_detect_truncated_file(
        self, simulated_cache: Path, monkeypatch
    ) -> None:
        """An empty filing.html should be flagged as corrupt."""
        # Corrupt one file.
        bad = simulated_cache / "MSFT" / "2024-06-30" / "filing.html"
        bad.write_text("", encoding="utf-8")

        quality = simulated_cache.parent / "quality"
        quality.mkdir()
        from omninexu.config import data_paths
        monkeypatch.setattr(
            type(data_paths), "quality_dir",
            property(lambda self, q=quality: q),
        )

        guard = PipelineGuard()
        corrupt = guard.check_cache(simulated_cache)
        assert len(corrupt) == 1
        assert "MSFT" in str(corrupt[0])

    def test_manifest_detects_tampered_file(
        self, simulated_cache: Path, monkeypatch
    ) -> None:
        """After manifest is generated, tampering should be detected."""
        quality = simulated_cache.parent / "quality"
        quality.mkdir()
        from omninexu.config import data_paths
        monkeypatch.setattr(
            type(data_paths), "quality_dir",
            property(lambda self, q=quality: q),
        )

        guard = PipelineGuard()
        guard.update_manifest(simulated_cache)

        # Tamper with a file.
        f = simulated_cache / "AAPL" / "2024-09-28" / "filing.html"
        f.write_text("TAMPERED CONTENT", encoding="utf-8")

        corrupt = guard.check_cache(simulated_cache)
        assert len(corrupt) == 1
        assert "AAPL" in str(corrupt[0])
