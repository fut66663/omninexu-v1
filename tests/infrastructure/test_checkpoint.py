"""Tests for CheckpointManager — JSONL-file-backed batch import progress tracking."""

import json
from pathlib import Path

import pytest

from omninexu.infrastructure.checkpoint import CheckpointManager


@pytest.fixture
def checkpoint_file(tmp_path: Path) -> Path:
    """Return a path to a temporary JSONL checkpoint file."""
    return tmp_path / "test_phase.json"


@pytest.fixture
def cpm(checkpoint_file: Path) -> CheckpointManager:
    """Return a fresh CheckpointManager for each test."""
    return CheckpointManager(checkpoint_file)


class TestMarkCompleted:
    """mark_completed() records successful progress."""

    def test_mark_completed_sets_status_ok(self, cpm):
        cpm.mark_completed("AAPL", "simfin", count=45)
        assert cpm.is_completed("AAPL", "simfin")

    def test_mark_completed_appends_to_file(self, cpm, checkpoint_file):
        cpm.mark_completed("AAPL", "simfin")
        cpm.mark_completed("MSFT", "simfin")

        lines = checkpoint_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        records = [json.loads(line) for line in lines]
        assert records[0]["ticker"] == "AAPL"
        assert records[0]["status"] == "ok"
        assert records[1]["ticker"] == "MSFT"
        assert records[1]["status"] == "ok"

    def test_mark_completed_stores_extra_meta(self, cpm, checkpoint_file):
        cpm.mark_completed("AAPL", "simfin", count=45, rows=3)

        lines = checkpoint_file.read_text(encoding="utf-8").strip().split("\n")
        record = json.loads(lines[0])
        assert record["count"] == 45
        assert record["rows"] == 3

    def test_mark_completed_overwrites_previous_entry(self, cpm):
        cpm.mark_failed("AAPL", "simfin", error="timeout")
        cpm.mark_completed("AAPL", "simfin")

        assert cpm.is_completed("AAPL", "simfin")
        assert len(cpm.get_failed("simfin")) == 0


class TestMarkFailed:
    """mark_failed() records failures for retry."""

    def test_mark_failed_not_completed(self, cpm):
        cpm.mark_failed("AAPL", "simfin", error="timeout")
        assert not cpm.is_completed("AAPL", "simfin")

    def test_mark_failed_stores_error(self, cpm, checkpoint_file):
        cpm.mark_failed("AAPL", "simfin", error="timeout")

        lines = checkpoint_file.read_text(encoding="utf-8").strip().split("\n")
        record = json.loads(lines[0])
        assert record["status"] == "failed"
        assert record["error"] == "timeout"


class TestIsCompleted:
    """is_completed() checks whether a ticker+phase has succeeded."""

    def test_is_completed_true(self, cpm):
        cpm.mark_completed("AAPL", "simfin")
        assert cpm.is_completed("AAPL", "simfin")

    def test_is_completed_false_for_unknown(self, cpm):
        assert not cpm.is_completed("AAPL", "simfin")

    def test_is_completed_false_for_failed(self, cpm):
        cpm.mark_failed("AAPL", "simfin", error="timeout")
        assert not cpm.is_completed("AAPL", "simfin")

    def test_is_completed_different_phase(self, cpm):
        cpm.mark_completed("AAPL", "simfin")
        assert not cpm.is_completed("AAPL", "edgar_13f")


class TestGetPending:
    """get_pending() returns tickers not yet completed."""

    def test_get_pending_all_when_none_completed(self, cpm):
        tickers = ["AAPL", "GOOGL", "MSFT"]
        pending = cpm.get_pending(tickers, "simfin")
        assert pending == tickers

    def test_get_pending_excludes_completed(self, cpm):
        cpm.mark_completed("AAPL", "simfin")
        tickers = ["AAPL", "GOOGL", "MSFT"]
        pending = cpm.get_pending(tickers, "simfin")
        assert pending == ["GOOGL", "MSFT"]

    def test_get_pending_does_not_exclude_failed(self, cpm):
        cpm.mark_failed("AAPL", "simfin", error="timeout")
        tickers = ["AAPL", "GOOGL"]
        pending = cpm.get_pending(tickers, "simfin")
        assert "AAPL" in pending  # Failed should be included as pending

    def test_get_pending_empty_tickers(self, cpm):
        assert cpm.get_pending([], "simfin") == []


class TestGetFailed:
    """get_failed() returns all failed entries for a phase."""

    def test_get_failed_empty(self, cpm):
        assert cpm.get_failed("simfin") == []

    def test_get_failed_returns_all(self, cpm):
        cpm.mark_failed("AAPL", "simfin", error="timeout")
        cpm.mark_failed("GOOGL", "simfin", error="parse error")
        cpm.mark_completed("MSFT", "simfin")

        failed = cpm.get_failed("simfin")
        assert len(failed) == 2
        tickers = {f["ticker"] for f in failed}
        assert tickers == {"AAPL", "GOOGL"}

    def test_get_failed_only_current_phase(self, cpm):
        cpm.mark_failed("AAPL", "simfin", error="timeout")
        cpm.mark_failed("GOOGL", "edgar_13f", error="not found")

        simfin_failed = cpm.get_failed("simfin")
        assert len(simfin_failed) == 1
        assert simfin_failed[0]["ticker"] == "AAPL"


class TestResetPhase:
    """reset_phase() removes all entries for a phase."""

    def test_reset_phase_removes_entries(self, cpm):
        cpm.mark_completed("AAPL", "simfin")
        cpm.mark_failed("GOOGL", "simfin", error="timeout")
        cpm.mark_completed("MSFT", "simfin")

        removed = cpm.reset_phase("simfin")
        assert removed == 3
        assert cpm.get_pending(["AAPL", "GOOGL", "MSFT"], "simfin") == ["AAPL", "GOOGL", "MSFT"]

    def test_reset_phase_only_affects_target_phase(self, cpm):
        cpm.mark_completed("AAPL", "simfin")
        cpm.mark_completed("GOOGL", "edgar_13f")

        removed = cpm.reset_phase("simfin")
        assert removed == 1
        assert not cpm.is_completed("AAPL", "simfin")
        assert cpm.is_completed("GOOGL", "edgar_13f")

    def test_reset_phase_empty_returns_zero(self, cpm):
        removed = cpm.reset_phase("nonexistent")
        assert removed == 0


class TestGetSummary:
    """get_summary() returns per-phase counts."""

    def test_get_summary_empty(self, cpm):
        assert cpm.get_summary() == {}

    def test_get_summary_counts(self, cpm):
        cpm.mark_completed("AAPL", "simfin")
        cpm.mark_completed("MSFT", "simfin")
        cpm.mark_failed("GOOGL", "simfin", error="parse error")

        summary = cpm.get_summary()
        assert "simfin" in summary
        assert summary["simfin"]["ok"] == 2
        assert summary["simfin"]["failed"] == 1

    def test_get_summary_skips_non_standard_status(self, checkpoint_file):
        """Entries with unknown/non-standard status should not increment counters.

        Branch coverage for checkpoint.py:89→85 — when ``status`` is not
        ``"ok"`` or ``"failed"`` (e.g. ``"pending"``, ``"unknown"``).
        """
        checkpoint_file.write_text(
            '{"ticker": "AAPL", "phase": "simfin", "status": "ok"}\n'
            '{"ticker": "GOOGL", "phase": "simfin", "status": "pending"}\n'
            '{"ticker": "MSFT", "phase": "simfin", "status": "unknown"}\n'
            '{"ticker": "NVDA", "phase": "simfin", "status": "failed", "error": "x"}\n',
            encoding="utf-8",
        )
        from omninexu.infrastructure.checkpoint import CheckpointManager

        cpm = CheckpointManager(checkpoint_file)
        summary = cpm.get_summary()
        assert summary["simfin"]["ok"] == 1
        assert summary["simfin"]["failed"] == 1
        # pending and unknown are not counted as ok or failed

    def test_get_summary_multiple_phases(self, cpm):
        cpm.mark_completed("AAPL", "simfin")
        cpm.mark_failed("GOOGL", "edgar_13f", error="timeout")

        summary = cpm.get_summary()
        assert summary["simfin"]["ok"] == 1
        assert summary["edgar_13f"]["failed"] == 1


class TestPersistence:
    """CheckpointManager persists state to JSONL file and reloads it."""

    def test_load_from_existing_file(self, checkpoint_file, tmp_path):
        """A new CheckpointManager should load entries written by a previous one."""
        cpm1 = CheckpointManager(checkpoint_file)
        cpm1.mark_completed("AAPL", "simfin")
        cpm1.mark_failed("GOOGL", "simfin", error="timeout")

        cpm2 = CheckpointManager(checkpoint_file)
        assert cpm2.is_completed("AAPL", "simfin")
        assert not cpm2.is_completed("GOOGL", "simfin")
        failed = cpm2.get_failed("simfin")
        assert len(failed) == 1
        assert failed[0]["ticker"] == "GOOGL"

    def test_load_empty_file(self, checkpoint_file):
        """A nonexistent file should initialize cleanly."""
        assert not checkpoint_file.exists()
        cpm = CheckpointManager(checkpoint_file)
        assert cpm.get_summary() == {}

    def test_load_skips_corrupt_lines(self, checkpoint_file):
        """Corrupt JSON lines should be skipped (crash-safe)."""
        checkpoint_file.write_text(
            '{"ticker": "AAPL", "phase": "simfin", "status": "ok"}\n'
            "this is not json\n"
            '{"ticker": "MSFT", "phase": "simfin", "status": "ok"}\n',
            encoding="utf-8",
        )

        cpm = CheckpointManager(checkpoint_file)
        assert cpm.is_completed("AAPL", "simfin")
        assert cpm.is_completed("MSFT", "simfin")

    def test_load_skips_empty_lines(self, checkpoint_file):
        """Empty lines should be ignored."""
        checkpoint_file.write_text(
            '\n'
            '{"ticker": "AAPL", "phase": "simfin", "status": "ok"}\n'
            '\n'
            '{"ticker": "MSFT", "phase": "simfin", "status": "ok"}\n'
            '\n',
            encoding="utf-8",
        )

        cpm = CheckpointManager(checkpoint_file)
        assert cpm.is_completed("AAPL", "simfin")
        assert cpm.is_completed("MSFT", "simfin")

    def test_last_write_wins_on_duplicate(self, checkpoint_file):
        """When a (ticker, phase) key appears twice, the last write wins."""
        checkpoint_file.write_text(
            '{"ticker": "AAPL", "phase": "simfin", "status": "failed", "error": "old"}\n'
            '{"ticker": "AAPL", "phase": "simfin", "status": "ok"}\n',
            encoding="utf-8",
        )

        cpm = CheckpointManager(checkpoint_file)
        assert cpm.is_completed("AAPL", "simfin")
        assert len(cpm.get_failed("simfin")) == 0

    def test_entries_record_timestamp(self, cpm, checkpoint_file):
        """Each entry should include an ISO 8601 timestamp."""
        cpm.mark_completed("AAPL", "simfin")

        lines = checkpoint_file.read_text(encoding="utf-8").strip().split("\n")
        record = json.loads(lines[0])
        assert "at" in record
        # Should be a valid ISO 8601 datetime string
        from datetime import datetime
        datetime.fromisoformat(record["at"])

    def test_flush_rewrites_clean_file(self, cpm, checkpoint_file):
        """After reset_phase, flush should produce a clean file."""
        cpm.mark_completed("AAPL", "simfin")
        cpm.mark_failed("GOOGL", "simfin", error="timeout")
        cpm.mark_completed("MSFT", "edgar_13f")

        cpm.reset_phase("simfin")

        # Reload from file
        cpm2 = CheckpointManager(checkpoint_file)
        summary = cpm2.get_summary()
        assert "simfin" not in summary
        assert summary["edgar_13f"]["ok"] == 1
