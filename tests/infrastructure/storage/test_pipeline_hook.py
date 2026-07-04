"""Tests for PipelineHook -- lightweight monitoring wrapper."""

from __future__ import annotations

from pathlib import Path

import pytest

from omninexu.infrastructure.storage.pipeline_hook import PipelineHook


@pytest.fixture
def log_dir(tmp_path: Path) -> Path:
    d = tmp_path / "logs"
    d.mkdir()
    return d


class TestPipelineHook:
    """Basic hook recording."""

    def test_record_download(self, log_dir: Path) -> None:
        hook = PipelineHook(log_dir)
        hook.record("download", "AAPL", ok=True, bytes_written=51200)
        hook.record("download", "MSFT", ok=True, bytes_written=48000)
        hook.log_summary()

    def test_record_all_steps(self, log_dir: Path) -> None:
        hook = PipelineHook(log_dir)
        hook.record("download", "AAPL", ok=True, bytes_written=50000)
        hook.record("parse", "AAPL", ok=True, facts_extracted=45)
        hook.record("save", "AAPL", ok=True, rows_inserted=45)
        hook.log_summary()

    def test_record_failure(self, log_dir: Path) -> None:
        hook = PipelineHook(log_dir)
        hook.record("download", "AAPL", ok=False, error="timeout")
        hook.log_summary()

    def test_unknown_step_warns(self, log_dir: Path) -> None:
        hook = PipelineHook(log_dir)
        # Unknown step type should not raise.
        hook.record("unknown", "AAPL")
