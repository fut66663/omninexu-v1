"""Tests for scripts/ingest/import_simfin.py."""

from datetime import date
from unittest.mock import patch

from omninexu.domain.financials import FinancialFact


class TestImportSimfin:
    def test_import_saves_facts(self):
        from scripts.ingest.import_simfin import import_simfin

        facts = [
            FinancialFact(
                ticker="AAPL",
                fiscal_year=2025,
                fiscal_period="FY",
                report_date=date(2025, 9, 27),
                concept="Revenue",
                value=416_161_000_000.0,
                unit="USD",
            ),
        ]

        with (
            patch("scripts.ingest.import_simfin.SessionLocal"),
            patch("scripts.ingest.import_simfin.FinancialsRepository") as mock_repo_cls,
            patch("scripts.ingest.import_simfin.SimFinAdapter") as mock_adapter_cls,
        ):
            mock_adapter = mock_adapter_cls.return_value
            mock_adapter.get_financial_facts.return_value = facts
            mock_repo = mock_repo_cls.return_value

            results = import_simfin(["AAPL"])
            assert results["AAPL"] == 1
            mock_repo.save_facts.assert_called_once_with(facts)

    def test_import_handles_failure(self):
        from scripts.ingest.import_simfin import import_simfin

        with (
            patch("scripts.ingest.import_simfin.SessionLocal"),
            patch("scripts.ingest.import_simfin.FinancialsRepository"),
            patch("scripts.ingest.import_simfin.SimFinAdapter") as mock_adapter_cls,
        ):
            mock_adapter = mock_adapter_cls.return_value
            mock_adapter.get_financial_facts.side_effect = RuntimeError("SimFin error")

            results = import_simfin(["AAPL"])
            assert results["AAPL"] == -1

    def test_import_empty_facts(self):
        from scripts.ingest.import_simfin import import_simfin

        with (
            patch("scripts.ingest.import_simfin.SessionLocal"),
            patch("scripts.ingest.import_simfin.FinancialsRepository"),
            patch("scripts.ingest.import_simfin.SimFinAdapter") as mock_adapter_cls,
        ):
            mock_adapter = mock_adapter_cls.return_value
            mock_adapter.get_financial_facts.return_value = []

            results = import_simfin(["AAPL"])
            assert results["AAPL"] == 0

    def test_import_default_tickers(self):
        from scripts.ingest.import_simfin import import_simfin

        with (
            patch("scripts.ingest.import_simfin.SessionLocal"),
            patch("scripts.ingest.import_simfin.FinancialsRepository"),
            patch("scripts.ingest.import_simfin.SimFinAdapter") as mock_adapter_cls,
        ):
            mock_adapter = mock_adapter_cls.return_value
            mock_adapter.get_financial_facts.return_value = []

            results = import_simfin()
            assert len(results) >= 10
