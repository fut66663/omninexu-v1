"""Tests for scripts/ingest/import_simfin_batch.py."""

import json
from datetime import date
from unittest.mock import patch

from omninexu.domain.financials import FinancialFact


def _make_universe_file(tmp_path, day=1, tickers=None):
    if tickers is None:
        tickers = [{"ticker": "AAPL", "cik": "0000320193", "name": "Apple Inc."}]
    path = tmp_path / f"sp500_universe_day{day}.json"
    path.write_text(json.dumps(tickers), encoding="utf-8")
    return path


class TestImportSimfinBatch:
    def test_imports_all_tickers(self, tmp_path):
        from scripts.ingest.import_simfin_batch import import_simfin_batch

        universe_dir = tmp_path / "universe"
        universe_dir.mkdir()
        _make_universe_file(universe_dir, day=1)

        with (
            patch("scripts.ingest.import_simfin_batch.UNIVERSE_DIR", universe_dir),
            patch("scripts.ingest.import_simfin_batch.SessionLocal"),
            patch("scripts.ingest.import_simfin_batch.FinancialsRepository"),
            patch("scripts.ingest.import_simfin_batch.SimFinAdapter") as mock_adapter_cls,
            patch("scripts.ingest.import_simfin_batch.CheckpointManager") as mock_cpm,
        ):
            mock_adapter = mock_adapter_cls.return_value
            mock_adapter.get_financial_facts.return_value = [
                FinancialFact(
                    ticker="AAPL",
                    fiscal_year=2024,
                    fiscal_period="FY",
                    report_date=date(2024, 9, 28),
                    concept="Revenue",
                    value=391_035_000_000.0,
                    unit="USD",
                ),
            ]

            cpm = mock_cpm.return_value
            cpm.get_pending.return_value = ["AAPL"]

            results = import_simfin_batch(day=1)
            assert results["AAPL"] == 1

    def test_returns_empty_when_all_complete(self, tmp_path):
        from scripts.ingest.import_simfin_batch import import_simfin_batch

        universe_dir = tmp_path / "universe"
        universe_dir.mkdir()
        _make_universe_file(universe_dir, day=1)

        with (
            patch("scripts.ingest.import_simfin_batch.UNIVERSE_DIR", universe_dir),
            patch("scripts.ingest.import_simfin_batch.SessionLocal"),
            patch("scripts.ingest.import_simfin_batch.FinancialsRepository"),
            patch("scripts.ingest.import_simfin_batch.SimFinAdapter"),
            patch("scripts.ingest.import_simfin_batch.CheckpointManager") as mock_cpm,
        ):
            cpm = mock_cpm.return_value
            cpm.get_pending.return_value = []  # nothing pending

            results = import_simfin_batch(day=1)
            assert results == {}

    def test_handles_adapter_failure(self, tmp_path):
        from scripts.ingest.import_simfin_batch import import_simfin_batch

        universe_dir = tmp_path / "universe"
        universe_dir.mkdir()
        _make_universe_file(universe_dir, day=1)

        with (
            patch("scripts.ingest.import_simfin_batch.UNIVERSE_DIR", universe_dir),
            patch("scripts.ingest.import_simfin_batch.SessionLocal"),
            patch("scripts.ingest.import_simfin_batch.FinancialsRepository"),
            patch("scripts.ingest.import_simfin_batch.SimFinAdapter") as mock_adapter_cls,
            patch("scripts.ingest.import_simfin_batch.CheckpointManager") as mock_cpm,
        ):
            mock_adapter = mock_adapter_cls.return_value
            mock_adapter.get_financial_facts.side_effect = RuntimeError("fail")

            cpm = mock_cpm.return_value
            cpm.get_pending.return_value = ["AAPL"]

            results = import_simfin_batch(day=1)
            assert results["AAPL"] == -1

    def test_retry_failed_mode(self, tmp_path):
        from scripts.ingest.import_simfin_batch import import_simfin_batch

        universe_dir = tmp_path / "universe"
        universe_dir.mkdir()
        _make_universe_file(universe_dir, day=1)

        with (
            patch("scripts.ingest.import_simfin_batch.UNIVERSE_DIR", universe_dir),
            patch("scripts.ingest.import_simfin_batch.SessionLocal"),
            patch("scripts.ingest.import_simfin_batch.FinancialsRepository"),
            patch("scripts.ingest.import_simfin_batch.SimFinAdapter") as mock_adapter_cls,
            patch("scripts.ingest.import_simfin_batch.CheckpointManager") as mock_cpm,
        ):
            mock_adapter = mock_adapter_cls.return_value
            mock_adapter.get_financial_facts.return_value = []

            cpm = mock_cpm.return_value
            cpm.get_failed.return_value = [{"ticker": "AAPL"}]
            cpm.get_pending.return_value = []

            results = import_simfin_batch(day=1, retry_failed=True)
            assert "AAPL" in results
