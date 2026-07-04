"""Tests for scripts/ingest/fill_edgar_zero_facts.py."""

from unittest.mock import patch

from scripts.ingest.fill_edgar_zero_facts import (
    _sanitize_ticker,
    fill_zero_facts,
)


class TestSanitizeTicker:
    def test_replaces_dot_with_dash(self):
        assert _sanitize_ticker("BRK.B") == "BRK-B"

    def test_preserves_normal_ticker(self):
        assert _sanitize_ticker("AAPL") == "AAPL"

    def test_handles_multiple_dots(self):
        assert _sanitize_ticker("A.B.C") == "A-B-C"

    def test_no_dots_no_change(self):
        assert _sanitize_ticker("MSFT") == "MSFT"


class TestFillZeroFacts:
    def test_returns_empty_when_no_zero_fact_companies(self):
        """When all companies have facts, fill_zero_facts returns {}."""
        with (
            patch("scripts.ingest.fill_edgar_zero_facts._get_zero_fact_tickers") as mock_tickers,
        ):
            mock_tickers.return_value = []
            result = fill_zero_facts()
            assert result == {}

    def test_dry_run_returns_empty(self):
        """Dry run should list tickers but return {}."""
        companies = [("AAPL", "0000320193", "Apple Inc.")]
        with (
            patch("scripts.ingest.fill_edgar_zero_facts._get_zero_fact_tickers") as mock_tickers,
        ):
            mock_tickers.return_value = companies
            result = fill_zero_facts(dry_run=True)
            assert result == {}

    def test_fill_imports_facts(self):
        """Successfully imports facts for zero-fact companies."""
        from datetime import date

        from omninexu.domain.financials import FinancialFact

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
            patch("scripts.ingest.fill_edgar_zero_facts._get_zero_fact_tickers") as mock_tickers,
            patch("scripts.ingest.fill_edgar_zero_facts.SessionLocal"),
            patch("scripts.ingest.fill_edgar_zero_facts.FinancialsRepository") as mock_repo_cls,
            patch("scripts.ingest.fill_edgar_zero_facts.EdgarClient") as mock_client_cls,
            patch("scripts.ingest.fill_edgar_zero_facts.CheckpointManager") as mock_cpm,
            patch("scripts.ingest.fill_edgar_zero_facts.time.sleep"),
        ):
            mock_tickers.return_value = companies
            mock_client = mock_client_cls.return_value
            mock_client.get_financial_facts.return_value = facts
            mock_repo = mock_repo_cls.return_value

            cpm = mock_cpm.return_value
            cpm.get_pending.return_value = ["AAPL"]

            result = fill_zero_facts()
            assert result["AAPL"] == 1
            mock_repo.save_facts.assert_called_once()

    def test_fill_handles_client_failure(self):
        """Failed downloads should be marked as -1."""
        companies = [("AAPL", "0000320193", "Apple Inc.")]

        with (
            patch("scripts.ingest.fill_edgar_zero_facts._get_zero_fact_tickers") as mock_tickers,
            patch("scripts.ingest.fill_edgar_zero_facts.SessionLocal"),
            patch("scripts.ingest.fill_edgar_zero_facts.FinancialsRepository"),
            patch("scripts.ingest.fill_edgar_zero_facts.EdgarClient") as mock_client_cls,
            patch("scripts.ingest.fill_edgar_zero_facts.CheckpointManager") as mock_cpm,
            patch("scripts.ingest.fill_edgar_zero_facts.time.sleep"),
        ):
            mock_tickers.return_value = companies
            mock_client = mock_client_cls.return_value
            mock_client.get_financial_facts.side_effect = RuntimeError("EDGAR down")

            cpm = mock_cpm.return_value
            cpm.get_pending.return_value = ["AAPL"]

            result = fill_zero_facts()
            assert result["AAPL"] == -1

    def test_fill_zero_facts_returned(self):
        """When EDGAR returns 0 facts, ticker is marked with 0 count."""
        companies = [("AAPL", "0000320193", "Apple Inc.")]

        with (
            patch("scripts.ingest.fill_edgar_zero_facts._get_zero_fact_tickers") as mock_tickers,
            patch("scripts.ingest.fill_edgar_zero_facts.SessionLocal"),
            patch("scripts.ingest.fill_edgar_zero_facts.FinancialsRepository"),
            patch("scripts.ingest.fill_edgar_zero_facts.EdgarClient") as mock_client_cls,
            patch("scripts.ingest.fill_edgar_zero_facts.CheckpointManager") as mock_cpm,
            patch("scripts.ingest.fill_edgar_zero_facts.time.sleep"),
        ):
            mock_tickers.return_value = companies
            mock_client = mock_client_cls.return_value
            mock_client.get_financial_facts.return_value = []

            cpm = mock_cpm.return_value
            cpm.get_pending.return_value = ["AAPL"]

            result = fill_zero_facts()
            assert result["AAPL"] == 0

    def test_retry_failed_mode(self):
        """--retry-failed uses get_failed instead of get_pending."""
        companies = [("AAPL", "0000320193", "Apple Inc.")]

        with (
            patch("scripts.ingest.fill_edgar_zero_facts._get_zero_fact_tickers") as mock_tickers,
            patch("scripts.ingest.fill_edgar_zero_facts.SessionLocal"),
            patch("scripts.ingest.fill_edgar_zero_facts.FinancialsRepository"),
            patch("scripts.ingest.fill_edgar_zero_facts.EdgarClient") as mock_client_cls,
            patch("scripts.ingest.fill_edgar_zero_facts.CheckpointManager") as mock_cpm,
            patch("scripts.ingest.fill_edgar_zero_facts.time.sleep"),
        ):
            mock_tickers.return_value = companies
            mock_client = mock_client_cls.return_value
            mock_client.get_financial_facts.return_value = []

            cpm = mock_cpm.return_value
            cpm.get_failed.return_value = [{"ticker": "AAPL"}]
            cpm.get_pending.return_value = []

            result = fill_zero_facts(retry_failed=True)
            assert "AAPL" in result

    def test_dual_class_ticker_sanitized(self):
        """BRK.B should be sanitized to BRK-B for EDGAR lookup."""
        companies = [("BRK.B", "0001067983", "Berkshire Hathaway")]

        with (
            patch("scripts.ingest.fill_edgar_zero_facts._get_zero_fact_tickers") as mock_tickers,
            patch("scripts.ingest.fill_edgar_zero_facts.SessionLocal"),
            patch("scripts.ingest.fill_edgar_zero_facts.FinancialsRepository"),
            patch("scripts.ingest.fill_edgar_zero_facts.EdgarClient") as mock_client_cls,
            patch("scripts.ingest.fill_edgar_zero_facts.CheckpointManager") as mock_cpm,
            patch("scripts.ingest.fill_edgar_zero_facts.time.sleep"),
        ):
            mock_tickers.return_value = companies
            mock_client = mock_client_cls.return_value
            mock_client.get_financial_facts.return_value = []

            cpm = mock_cpm.return_value
            cpm.get_pending.return_value = ["BRK.B"]

            fill_zero_facts()
            # Should have been called with sanitized ticker "BRK-B"
            mock_client.get_financial_facts.assert_called_with("BRK-B", num_filings=1)
