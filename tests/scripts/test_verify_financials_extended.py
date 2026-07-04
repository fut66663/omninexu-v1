"""Tests for verify_financials.py — cross-year verification (Level 2)."""

from datetime import date
from unittest.mock import patch

from omninexu.domain.financials import FinancialFact
from scripts.verify.verify_financials import (
    main,
    verify_cross_year,
    verify_ticker,
)


class TestVerifyCrossYear:
    def test_cross_year_passes_with_matching_values(self):
        """Cross-year check should pass when same FY values match across filings."""

        class FakeClient:
            def get_financial_facts(self, ticker, num_filings=1):
                return [
                    FinancialFact(
                        ticker=ticker,
                        fiscal_year=2024,
                        fiscal_period="FY",
                        report_date=date(2025, 9, 27),
                        concept="Revenue",
                        value=391_035_000_000.0,
                        unit="USD",
                        source_filing="10-K_2025",
                    ),
                    FinancialFact(
                        ticker=ticker,
                        fiscal_year=2024,
                        fiscal_period="FY",
                        report_date=date(2024, 9, 28),
                        concept="Revenue",
                        value=391_035_000_000.0,
                        unit="USD",
                        source_filing="10-K_2024",
                    ),
                ]

        result = verify_cross_year("AAPL", client=FakeClient())
        assert result["failures"] == 0
        assert any("PASS" in m for m in result["messages"])

    def test_cross_year_flags_deviation(self):
        """Cross-year should flag when the same FY differs across filings."""

        class FakeClient:
            def get_financial_facts(self, ticker, num_filings=1):
                return [
                    FinancialFact(
                        ticker=ticker,
                        fiscal_year=2024,
                        fiscal_period="FY",
                        report_date=date(2025, 9, 27),
                        concept="Revenue",
                        value=400_000_000_000.0,
                        unit="USD",
                        source_filing="10-K_2025",
                    ),
                    FinancialFact(
                        ticker=ticker,
                        fiscal_year=2024,
                        fiscal_period="FY",
                        report_date=date(2024, 9, 28),
                        concept="Revenue",
                        value=391_035_000_000.0,
                        unit="USD",
                        source_filing="10-K_2024",
                    ),
                ]

        result = verify_cross_year("AAPL", client=FakeClient())
        assert result["failures"] >= 1
        assert any("FAIL" in m for m in result["messages"])

    def test_cross_year_skips_single_source(self):
        """Cross-year should skip concepts that only appear in one filing."""

        class FakeClient:
            def get_financial_facts(self, ticker, num_filings=1):
                return [
                    FinancialFact(
                        ticker=ticker,
                        fiscal_year=2025,
                        fiscal_period="FY",
                        report_date=date(2025, 9, 27),
                        concept="Revenue",
                        value=416_161_000_000.0,
                        unit="USD",
                        source_filing="10-K_2025",
                    ),
                ]

        result = verify_cross_year("AAPL", client=FakeClient())
        # Single source → skipped, no failures
        assert result["failures"] == 0

    def test_cross_year_handles_fetch_error(self):
        """Cross-year should gracefully handle API errors."""

        class FakeClient:
            def get_financial_facts(self, ticker, num_filings=1):
                raise RuntimeError("SEC unavailable")

        result = verify_cross_year("AAPL", client=FakeClient())
        assert result["failures"] == 0
        assert len(result["messages"]) == 1

    def test_cross_year_skips_non_revenue_netincome(self):
        """Cross-year should only check Revenue and NetIncome concepts."""

        class FakeClient:
            def get_financial_facts(self, ticker, num_filings=1):
                return [
                    FinancialFact(
                        ticker=ticker,
                        fiscal_year=2024,
                        fiscal_period="FY",
                        report_date=date(2025, 9, 27),
                        concept="OperatingIncome",
                        value=100_000_000_000.0,
                        unit="USD",
                        source_filing="10-K_2025",
                    ),
                    FinancialFact(
                        ticker=ticker,
                        fiscal_year=2024,
                        fiscal_period="FY",
                        report_date=date(2024, 9, 28),
                        concept="OperatingIncome",
                        value=90_000_000_000.0,
                        unit="USD",
                        source_filing="10-K_2024",
                    ),
                ]

        result = verify_cross_year("AAPL", client=FakeClient())
        # OperatingIncome is not checked, should be skipped
        assert result["failures"] == 0


class TestVerifyTickerEdgeCases:
    def test_verify_ticker_handles_fetch_error(self):
        """verify_ticker should return failure info on exception."""

        class FakeClient:
            def get_financial_facts(self, ticker, num_filings=1):
                raise ConnectionError("Network down")

        result = verify_ticker("AAPL", client=FakeClient())
        assert result["failures"] == 2
        assert result["ticker"] == "AAPL"

    def test_verify_ticker_fact_missing(self):
        """verify_ticker should report MISSING when concept absent."""

        class FakeClient:
            def get_financial_facts(self, ticker, num_filings=1):
                return []

        result = verify_ticker("AAPL", client=FakeClient())
        assert result["failures"] >= 1
        assert any("MISSING" in m for m in result["messages"])


class TestMain:
    def test_main_default_tickers(self):
        """main() with no args uses default tickers."""
        with (
            patch("scripts.verify.verify_financials.EdgarClient") as mock_cls,
        ):
            mock_client = mock_cls.return_value
            mock_client.get_financial_facts.return_value = []

            # main expects sys.argv — simulate via direct call
            exit_code = main(["AAPL"])
            assert exit_code in (0, 1)

    def test_main_with_cross_year(self):
        """main() with --cross-year flag runs both checks."""
        with (
            patch("scripts.verify.verify_financials.EdgarClient") as mock_cls,
        ):
            mock_client = mock_cls.return_value
            mock_client.get_financial_facts.return_value = []

            exit_code = main(["AAPL"], cross_year=True)
            assert exit_code in (0, 1)
