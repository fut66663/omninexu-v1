"""Tests for scripts/ingest/sync_edgar_current.py."""

from datetime import date
from unittest.mock import patch

from omninexu.domain.financials import FinancialFact
from scripts.ingest.sync_edgar_current import sync_edgar_current


class TestSyncEdgarCurrent:
    def test_returns_empty_on_dry_run(self):
        with (
            patch("scripts.ingest.sync_edgar_current._get_all_tickers") as mock_tickers,
        ):
            mock_tickers.return_value = [("AAPL", "0000320193", "Apple Inc.")]
            result = sync_edgar_current(dry_run=True)
            assert result == {}

    def test_sync_imports_facts(self):
        companies = [("AAPL", "0000320193", "Apple Inc.")]
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
            patch("scripts.ingest.sync_edgar_current._get_all_tickers") as mock_tickers,
            patch("scripts.ingest.sync_edgar_current.SessionLocal"),
            patch("scripts.ingest.sync_edgar_current.FinancialsRepository") as mock_repo_cls,
            patch("scripts.ingest.sync_edgar_current.EdgarClient") as mock_client_cls,
            patch("scripts.ingest.sync_edgar_current.CheckpointManager") as mock_cpm,
            patch("scripts.ingest.sync_edgar_current.time.sleep"),
        ):
            mock_tickers.return_value = companies
            mock_client = mock_client_cls.return_value
            mock_client.get_financial_facts.return_value = facts
            mock_repo = mock_repo_cls.return_value

            cpm = mock_cpm.return_value
            cpm.get_pending.return_value = ["AAPL"]

            result = sync_edgar_current()
            assert result["AAPL"] == 1
            mock_repo.save_facts.assert_called_once()

    def test_sync_returns_empty_when_all_complete(self):
        companies = [("AAPL", "0000320193", "Apple Inc.")]

        with (
            patch("scripts.ingest.sync_edgar_current._get_all_tickers") as mock_tickers,
            patch("scripts.ingest.sync_edgar_current.SessionLocal"),
            patch("scripts.ingest.sync_edgar_current.FinancialsRepository"),
            patch("scripts.ingest.sync_edgar_current.EdgarClient"),
            patch("scripts.ingest.sync_edgar_current.CheckpointManager") as mock_cpm,
        ):
            mock_tickers.return_value = companies
            cpm = mock_cpm.return_value
            cpm.get_pending.return_value = []

            result = sync_edgar_current()
            assert result == {}

    def test_sync_handles_client_failure(self):
        companies = [("AAPL", "0000320193", "Apple Inc.")]

        with (
            patch("scripts.ingest.sync_edgar_current._get_all_tickers") as mock_tickers,
            patch("scripts.ingest.sync_edgar_current.SessionLocal"),
            patch("scripts.ingest.sync_edgar_current.FinancialsRepository"),
            patch("scripts.ingest.sync_edgar_current.EdgarClient") as mock_client_cls,
            patch("scripts.ingest.sync_edgar_current.CheckpointManager") as mock_cpm,
            patch("scripts.ingest.sync_edgar_current.time.sleep"),
        ):
            mock_tickers.return_value = companies
            mock_client = mock_client_cls.return_value
            mock_client.get_financial_facts.side_effect = RuntimeError("EDGAR down")

            cpm = mock_cpm.return_value
            cpm.get_pending.return_value = ["AAPL"]

            result = sync_edgar_current()
            assert result["AAPL"] == -1

    def test_sync_rewrites_ticker_for_alias(self):
        """Dual-class tickers like BRK.B should have facts rewritten."""
        companies = [("BRK.B", "0001067983", "Berkshire Hathaway")]

        facts = [
            FinancialFact(
                ticker="BRK-A",  # returned as alias
                fiscal_year=2025,
                fiscal_period="FY",
                report_date=date(2025, 12, 31),
                concept="Revenue",
                value=300_000_000_000.0,
                unit="USD",
            ),
        ]

        with (
            patch("scripts.ingest.sync_edgar_current._get_all_tickers") as mock_tickers,
            patch("scripts.ingest.sync_edgar_current.SessionLocal"),
            patch("scripts.ingest.sync_edgar_current.FinancialsRepository") as mock_repo_cls,
            patch("scripts.ingest.sync_edgar_current.EdgarClient") as mock_client_cls,
            patch("scripts.ingest.sync_edgar_current.CheckpointManager") as mock_cpm,
            patch("scripts.ingest.sync_edgar_current.time.sleep"),
        ):
            mock_tickers.return_value = companies
            mock_client = mock_client_cls.return_value
            mock_client.get_financial_facts.return_value = facts
            mock_repo = mock_repo_cls.return_value

            cpm = mock_cpm.return_value
            cpm.get_pending.return_value = ["BRK.B"]

            result = sync_edgar_current()
            # Facts should have ticker rewritten from BRK-A → BRK.B
            saved_facts = mock_repo.save_facts.call_args[0][0]
            assert all(f.ticker == "BRK.B" for f in saved_facts)
            assert result["BRK.B"] == 1

    def test_sync_retry_failed_mode(self):
        companies = [("AAPL", "0000320193", "Apple Inc.")]

        with (
            patch("scripts.ingest.sync_edgar_current._get_all_tickers") as mock_tickers,
            patch("scripts.ingest.sync_edgar_current.SessionLocal"),
            patch("scripts.ingest.sync_edgar_current.FinancialsRepository"),
            patch("scripts.ingest.sync_edgar_current.EdgarClient") as mock_client_cls,
            patch("scripts.ingest.sync_edgar_current.CheckpointManager") as mock_cpm,
            patch("scripts.ingest.sync_edgar_current.time.sleep"),
        ):
            mock_tickers.return_value = companies
            mock_client = mock_client_cls.return_value
            mock_client.get_financial_facts.return_value = []

            cpm = mock_cpm.return_value
            cpm.get_failed.return_value = [{"ticker": "AAPL"}]
            cpm.get_pending.return_value = []

            result = sync_edgar_current(retry_failed=True)
            assert "AAPL" in result

    def test_sync_zero_facts_returned(self):
        """When EDGAR returns 0 facts, ticker gets count 0."""
        companies = [("AAPL", "0000320193", "Apple Inc.")]

        with (
            patch("scripts.ingest.sync_edgar_current._get_all_tickers") as mock_tickers,
            patch("scripts.ingest.sync_edgar_current.SessionLocal"),
            patch("scripts.ingest.sync_edgar_current.FinancialsRepository"),
            patch("scripts.ingest.sync_edgar_current.EdgarClient") as mock_client_cls,
            patch("scripts.ingest.sync_edgar_current.CheckpointManager") as mock_cpm,
            patch("scripts.ingest.sync_edgar_current.time.sleep"),
        ):
            mock_tickers.return_value = companies
            mock_client = mock_client_cls.return_value
            mock_client.get_financial_facts.return_value = []

            cpm = mock_cpm.return_value
            cpm.get_pending.return_value = ["AAPL"]

            result = sync_edgar_current()
            assert result["AAPL"] == 0
