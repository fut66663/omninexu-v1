"""Tests for multi-filing historical 10-K download."""

from datetime import date
from unittest.mock import MagicMock, patch

import httpx
import pandas as pd
import pytest
from edgar import Company, CompanyNotFoundError

from omninexu.domain.financials import FinancialFact
from omninexu.infrastructure.clients import EdgarClient
from omninexu.infrastructure.clients.edgar_historical import fetch_historical_filings
from omninexu.observability import EdgarRateLimitError, TickerNotFoundError


class TestEdgarClientMultiFiling:
    """Unit tests for historical multi-filing download (num_filings > 1)."""

    # ── mock helpers ──────────────────────────────────────────────────

    @staticmethod
    def _make_filing(year: int, revenue: float, net_income: float,
                     accession: str, period: str) -> MagicMock:
        """Build one mock 10-K filing with current + prior year comparison columns."""
        cur = f"{year}-09-27 (FY)"
        pri = f"{year - 1}-09-28 (FY)"

        income = pd.DataFrame({
            "concept": [
                "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax",
                "us-gaap_NetIncomeLoss",
            ],
            "label": ["Net sales", "Net income"],
            cur: [revenue, net_income],
            pri: [revenue * 0.9, net_income * 0.9],
            "dimension": [False, False],
            "is_breakdown": [False, False],
        })
        balance = pd.DataFrame({
            "concept": ["us-gaap_Assets"],
            "label": ["Total assets"],
            cur: [300_000_000_000.0],
            "dimension": [False],
            "is_breakdown": [False],
        })
        cashflow = pd.DataFrame({
            "concept": ["us-gaap_NetCashProvidedByUsedInOperatingActivities"],
            "label": ["Operating cash flow"],
            cur: [100_000_000_000.0],
            "dimension": [False],
            "is_breakdown": [False],
        })

        tenk = MagicMock()
        tenk.income_statement.to_dataframe.return_value = income
        tenk.balance_sheet.to_dataframe.return_value = balance
        tenk.cash_flow_statement.to_dataframe.return_value = cashflow

        f = MagicMock()
        f.period_of_report = period
        f.accession_no = accession
        f.filing_date = date(year, 11, 7)
        f.obj.return_value = tenk
        f.text.return_value = f"<html>10-K {period}</html>"
        return f

    @staticmethod
    def _make_company(filings: list[MagicMock]) -> MagicMock:
        """Build a mock edgartools Company whose get_filings returns *filings*."""
        c = MagicMock()
        c.cik = "0000320193"
        c.name = "Apple Inc."
        c.sic = "3571"
        c.get_filings.return_value.latest.return_value = filings
        return c

    # ── tests ─────────────────────────────────────────────────────────

    def test_combined_facts_from_multiple_years(self) -> None:
        """3 filings → facts spanning multiple fiscal years."""
        f1 = self._make_filing(2025, 416e9, 112e9, "0000320193-25-000079", "2025-09-27")
        f2 = self._make_filing(2024, 391e9, 93.7e9, "0000320193-24-000079", "2024-09-28")
        f3 = self._make_filing(2023, 383e9, 96.9e9, "0000320193-23-000079", "2023-09-30")

        with patch("omninexu.infrastructure.clients.edgar_client.Company",
                   return_value=self._make_company([f1, f2, f3])):
            facts = EdgarClient().get_financial_facts("AAPL", num_filings=3)

        rev_years = sorted({f.fiscal_year for f in facts if f.concept == "Revenue"})
        assert len(rev_years) >= 3, f"Expected ≥3 Revenue years, got {rev_years}"
        assert all(isinstance(f, FinancialFact) for f in facts)

    def test_one_filing_failure_does_not_kill_batch(self) -> None:
        """One corrupt filing → other filings still produce facts."""
        f1 = self._make_filing(2025, 416e9, 112e9, "0000320193-25-000079", "2025-09-27")
        f2 = self._make_filing(2024, 391e9, 93.7e9, "0000320193-24-000079", "2024-09-28")
        f2.obj.side_effect = RuntimeError("XBRL parse error")
        f3 = self._make_filing(2023, 383e9, 96.9e9, "0000320193-23-000079", "2023-09-30")

        with patch("omninexu.infrastructure.clients.edgar_client.Company",
                   return_value=self._make_company([f1, f2, f3])):
            facts = EdgarClient().get_financial_facts("AAPL", num_filings=3)

        assert len(facts) > 0, "Should have facts from successful filings"

    def test_amended_filing_deduplicated(self) -> None:
        """10-K and 10-K/A sharing same period → only first (most recent) kept."""
        f_amended = self._make_filing(2025, 416.2e9, 112.05e9,
                                      "0000320193-25-000080", "2025-09-27")
        f_original = self._make_filing(2025, 416.1e9, 112.01e9,
                                       "0000320193-25-000079", "2025-09-27")
        f_old = self._make_filing(2024, 391e9, 93.7e9,
                                  "0000320193-24-000079", "2024-09-28")

        with patch("omninexu.infrastructure.clients.edgar_client.Company",
                   return_value=self._make_company([f_amended, f_original, f_old])):
            facts = EdgarClient().get_financial_facts("AAPL", num_filings=3)

        sources = {f.source_filing for f in facts}
        assert "0000320193-25-000080" in sources, "Amended filing should be used"
        assert "0000320193-25-000079" not in sources, "Original should be skipped"

    def test_default_single_filing_unchanged(self) -> None:
        """num_filings=1 (default) behaves identically to Week 1."""
        from tests.infrastructure.clients.test_edgar_client import TestEdgarClientUnit

        mock_co = TestEdgarClientUnit._make_mock_company()
        with patch("omninexu.infrastructure.clients.edgar_client.Company",
                   return_value=mock_co):
            facts = EdgarClient().get_financial_facts("AAPL")

        rev = next((f for f in facts if f.concept == "Revenue" and f.fiscal_year == 2025), None)
        assert rev is not None
        assert rev.value == pytest.approx(416161000000.0)


class TestFetchHistoricalErrorHandling:
    """Tests for error conversion in fetch_historical_filings()."""

    def test_company_not_found_converts_to_ticker_not_found(self) -> None:
        """CompanyNotFoundError → TickerNotFoundError."""
        mock_company = MagicMock(spec=Company)
        mock_company.get_filings.side_effect = CompanyNotFoundError("INVALID")

        with pytest.raises(TickerNotFoundError):
            fetch_historical_filings(
                mock_company, "INVALID", num_filings=3, parse_date=lambda x: date.today()
            )

    def test_http_error_converts_to_rate_limit(self) -> None:
        """httpx.HTTPError → EdgarRateLimitError."""
        mock_company = MagicMock(spec=Company)
        mock_company.get_filings.side_effect = httpx.HTTPError("429 Too Many Requests")

        with pytest.raises(EdgarRateLimitError):
            fetch_historical_filings(
                mock_company, "AAPL", num_filings=3, parse_date=lambda x: date.today()
            )


class TestEdgarHistoricalBranchCoverage:
    """Tests covering branch edges in edgar_historical.py."""

    def test_missing_statement_type_skipped(self) -> None:
        """10-K missing a statement type (e.g. no balance_sheet) should not crash.

        Branch coverage for edgar_historical.py:74→68 — ``getattr(tenk, attr,
        None)`` returns None so the for-loop continues to the next type.
        """
        income = pd.DataFrame({
            "concept": ["us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax"],
            "label": ["Net sales"],
            "2025-09-27 (FY)": [416e9],
            "dimension": [False],
            "is_breakdown": [False],
        })

        # Use a plain class with __getattr__ so missing attributes return None
        class PartialTenk:
            def __init__(self):
                self.income_statement = MagicMock()
                self.income_statement.to_dataframe.return_value = income

            # getattr returns None for anything not explicitly set
            def __getattr__(self, name):
                return None

        tenk = PartialTenk()

        f = MagicMock()
        f.period_of_report = "2025-09-27"
        f.accession_no = "ACC-001"
        f.filing_date = date(2025, 11, 7)
        f.obj.return_value = tenk
        f.text.return_value = "<html>10-K</html>"

        c = MagicMock()
        c.cik = "CIK"
        c.name = "Test"
        c.sic = "SIC"
        c.get_filings.return_value.latest.return_value = [f]

        # num_filings=2 triggers the fetch_historical_10k_statements path
        with patch("omninexu.infrastructure.clients.edgar_client.Company", return_value=c):
            facts = EdgarClient().get_financial_facts("AAPL", num_filings=2)

        # Should produce income facts only; balance/cashflow skipped without error
        assert all(f.statement_type == "income" for f in facts)
        assert len(facts) > 0
