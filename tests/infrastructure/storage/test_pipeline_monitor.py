"""Tests for PipelineMonitor -- structured ingestion step logging."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from omninexu.infrastructure.storage.pipeline_monitor import PipelineMonitor


@pytest.fixture
def log_dir(tmp_path: Path) -> Path:
    """Temporary log directory."""
    d = tmp_path / "logs" / "ingestion"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def monitor(log_dir: Path) -> PipelineMonitor:
    """Fresh PipelineMonitor writing to a temp directory."""
    return PipelineMonitor(log_dir)


class TestRecordSteps:
    """Download / parse / save recording."""

    def test_record_download_writes_json_line(self, monitor: PipelineMonitor, log_dir: Path) -> None:
        rid = monitor.start_run()
        monitor.record_download(
            rid, source="edgar", ticker="AAPL", form="10-K",
            status="ok", duration_ms=812, bytes_written=51200,
            checksum="sha256:abc123",
        )

        lines = _read_log_lines(log_dir)
        assert len(lines) == 1
        entry = lines[0]
        assert entry["run_id"] == rid
        assert entry["step"] == "download"
        assert entry["ticker"] == "AAPL"
        assert entry["status"] == "ok"
        assert entry["bytes_written"] == 51200
        assert entry["checksum"] == "sha256:abc123"

    def test_record_parse_writes_json_line(self, monitor: PipelineMonitor, log_dir: Path) -> None:
        rid = monitor.start_run()
        monitor.record_parse(
            rid, source="edgar", ticker="AAPL", form="10-K",
            status="ok", duration_ms=234, facts_extracted=45,
        )

        lines = _read_log_lines(log_dir)
        assert len(lines) == 1
        assert lines[0]["step"] == "parse"
        assert lines[0]["facts_extracted"] == 45

    def test_record_save_writes_json_line(self, monitor: PipelineMonitor, log_dir: Path) -> None:
        rid = monitor.start_run()
        monitor.record_save(
            rid, source="edgar", ticker="AAPL",
            status="ok", duration_ms=56, rows_inserted=45,
        )

        lines = _read_log_lines(log_dir)
        assert len(lines) == 1
        assert lines[0]["step"] == "save"
        assert lines[0]["rows_inserted"] == 45

    def test_multiple_entries_in_one_run(self, monitor: PipelineMonitor, log_dir: Path) -> None:
        rid = monitor.start_run()
        monitor.record_download(rid, source="edgar", ticker="AAPL", form="10-K",
                                status="ok", duration_ms=100, bytes_written=1000)
        monitor.record_parse(rid, source="edgar", ticker="AAPL", form="10-K",
                             status="ok", duration_ms=200, facts_extracted=9)
        monitor.record_save(rid, source="edgar", ticker="AAPL",
                            status="ok", duration_ms=50, rows_inserted=9)

        lines = _read_log_lines(log_dir)
        assert len(lines) == 3
        steps = [e["step"] for e in lines]
        assert steps == ["download", "parse", "save"]


class TestRunSummary:
    """Per-run aggregation."""

    def test_empty_summary_for_unknown_run(self, monitor: PipelineMonitor) -> None:
        summary = monitor.get_run_summary("nonexistent")
        assert summary["entries"] == 0

    def test_summary_counts_steps(self, monitor: PipelineMonitor, log_dir: Path) -> None:
        rid = monitor.start_run()
        monitor.record_download(rid, source="edgar", ticker="AAPL", form="10-K",
                                status="ok", duration_ms=100, bytes_written=1000)
        monitor.record_download(rid, source="edgar", ticker="MSFT", form="10-K",
                                status="ok", duration_ms=200, bytes_written=2000)

        summary = monitor.get_run_summary(rid)
        assert summary["entries"] == 2
        assert summary["tickers"] == 2
        assert summary["steps"]["download"] == 2
        assert summary["steps"]["parse"] == 0
        assert summary["failed"] == 0
        assert summary["total_bytes"] == 3000

    def test_summary_counts_failures(self, monitor: PipelineMonitor, log_dir: Path) -> None:
        rid = monitor.start_run()
        monitor.record_download(rid, source="edgar", ticker="AAPL", form="10-K",
                                status="failed", duration_ms=5000, bytes_written=0)
        monitor.record_download(rid, source="edgar", ticker="MSFT", form="10-K",
                                status="ok", duration_ms=100, bytes_written=1000)

        summary = monitor.get_run_summary(rid)
        assert summary["failed"] == 1

    def test_summary_aggregates_facts(self, monitor: PipelineMonitor, log_dir: Path) -> None:
        rid = monitor.start_run()
        monitor.record_parse(rid, source="edgar", ticker="AAPL", form="10-K",
                             status="ok", duration_ms=100, facts_extracted=20)
        monitor.record_save(rid, source="edgar", ticker="AAPL",
                            status="ok", duration_ms=50, rows_inserted=20)

        summary = monitor.get_run_summary(rid)
        assert summary["total_facts"] == 40


class TestHealthReport:
    """Health report across recent days."""

    def test_health_report_basic(self, monitor: PipelineMonitor, log_dir: Path) -> None:
        rid = monitor.start_run()
        monitor.record_download(rid, source="edgar", ticker="AAPL", form="10-K",
                                status="ok", duration_ms=100, bytes_written=1000)

        report = monitor.get_health_report(days=30)
        assert report["total_entries"] == 1
        assert report["ok"] == 1
        assert report["failed"] == 0
        assert report["success_rate"] == 100.0

    def test_health_report_no_entries(self, monitor: PipelineMonitor) -> None:
        report = monitor.get_health_report(days=30)
        assert report["total_entries"] == 0
        assert report["success_rate"] == 0.0


class TestStartRun:
    """Run ID generation."""

    def test_start_run_returns_unique_ids(self) -> None:
        ids = {PipelineMonitor.start_run() for _ in range(100)}
        assert len(ids) == 100

    def test_start_run_returns_12_char_hex(self) -> None:
        rid = PipelineMonitor.start_run()
        assert len(rid) == 12
        assert all(c in "0123456789abcdef" for c in rid)


# -- helpers ------------------------------------------------------------

def _read_log_lines(log_dir: Path) -> list[dict]:
    """Read all JSON lines from the current month's log file."""
    month_file = next(log_dir.glob("*.jsonl"))
    entries = []
    for line in month_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries
