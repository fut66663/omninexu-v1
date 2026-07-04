"""Tests for EdgarClient."""

from datetime import date
from unittest.mock import MagicMock, patch

import httpx
import pandas as pd
import pytest
from edgar import CompanyNotFoundError

from omninexu.domain.financials import FinancialFact
from omninexu.infrastructure.clients import EdgarClient
from omninexu.observability import EdgarRateLimitError, TickerNotFoundError


@pytest.mark.integration
class TestEdgarClientIntegration:
    """Integration tests that call SEC EDGAR."""

    def test_get_financial_facts_aapl_returns_facts(self) -> None:
        """AAPL latest 10-K should produce non-empty facts."""
        client = EdgarClient()
        facts = client.get_financial_facts("AAPL")

        assert len(facts) > 0
        assert all(f.ticker == "AAPL" for f in facts)

    def test_get_financial_facts_aapl_has_revenue(self) -> None:
        """AAPL facts should include Revenue."""
        client = EdgarClient()
        facts = client.get_financial_facts("AAPL")

        revenue_facts = [f for f in facts if f.concept == "Revenue"]
        assert revenue_facts, "Expected at least one Revenue fact"

    def test_get_financial_facts_aapl_revenue_fy2025_accuracy(self) -> None:
        """AAPL FY2025 Revenue should match official 10-K within 0.01%."""
        client = EdgarClient()
        facts = client.get_financial_facts("AAPL")

        revenue = next(
            (f for f in facts if f.concept == "Revenue" and f.fiscal_year == 2025),
            None,
        )
        assert revenue is not None, "Expected FY2025 Revenue fact"

        expected_revenue = 416_161_000_000
        assert abs(revenue.value - expected_revenue) / expected_revenue < 0.0001

    def test_get_financial_facts_aapl_netincome_fy2025_accuracy(self) -> None:
        """AAPL FY2025 NetIncome should match official 10-K within 0.01%."""
        client = EdgarClient()
        facts = client.get_financial_facts("AAPL")

        net_income = next(
            (f for f in facts if f.concept == "NetIncome" and f.fiscal_year == 2025),
            None,
        )
        assert net_income is not None, "Expected FY2025 NetIncome fact"

        expected_net_income = 112_010_000_000
        assert abs(net_income.value - expected_net_income) / expected_net_income < 0.0001

    def test_get_financial_facts_invalid_ticker_raises(self) -> None:
        """Invalid ticker should raise TickerNotFoundError."""
        client = EdgarClient()

        with pytest.raises(TickerNotFoundError):
            client.get_financial_facts("INVALID_TICKER_XYZ")


class TestEdgarClientUnit:
    """Unit tests for EdgarClient using mocked edgartools responses."""

    @staticmethod
    def _make_mock_company() -> MagicMock:
        """Build a mock edgartools Company with one 10-K filing."""
        income_df = pd.DataFrame(
            {
                "concept": [
                    "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax",
                    "us-gaap_NetIncomeLoss",
                ],
                "label": ["Net sales", "Net income"],
                "2025-09-27 (FY)": [416161000000.0, 112010000000.0],
                "2024-09-28 (FY)": [391035000000.0, 93736000000.0],
                "dimension": [False, False],
                "is_breakdown": [False, False],
            }
        )
        balance_df = pd.DataFrame(
            {
                "concept": ["us-gaap_Assets"],
                "label": ["Total assets"],
                "2025-09-27 (FY)": [364980000000.0],
                "dimension": [False],
                "is_breakdown": [False],
            }
        )
        cashflow_df = pd.DataFrame(
            {
                "concept": ["us-gaap_NetCashProvidedByUsedInOperatingActivities"],
                "label": ["Operating cash flow"],
                "2025-09-27 (FY)": [118254000000.0],
                "dimension": [False],
                "is_breakdown": [False],
            }
        )

        tenk = MagicMock()
        tenk.income_statement.to_dataframe.return_value = income_df
        tenk.balance_sheet.to_dataframe.return_value = balance_df
        tenk.cash_flow_statement.to_dataframe.return_value = cashflow_df

        filing = MagicMock()
        filing.period_of_report = "2025-09-27"
        filing.accession_no = "0000320193-25-000079"
        filing.filing_date = date(2025, 11, 7)
        filing.obj.return_value = tenk

        filings = MagicMock()
        filings.latest.return_value = filing

        company = MagicMock()
        company.cik = "0000320193"
        company.name = "Apple Inc."
        company.sic = "3571"
        company.get_filings.return_value = filings

        return company

    def test_get_company_info(self) -> None:
        """get_company_info should return ticker, cik, name and sic."""
        client = EdgarClient()
        mock_company = self._make_mock_company()

        with patch("omninexu.infrastructure.clients.edgar_client.Company", return_value=mock_company):
            info = client.get_company_info("AAPL")

        assert info == {
            "ticker": "AAPL",
            "cik": "0000320193",
            "name": "Apple Inc.",
            "sic": "3571",
        }

    def test_get_financial_facts_returns_standardized_facts(self) -> None:
        """get_financial_facts should return FinancialFact objects with correct concepts."""
        client = EdgarClient()
        mock_company = self._make_mock_company()

        with patch("omninexu.infrastructure.clients.edgar_client.Company", return_value=mock_company):
            facts = client.get_financial_facts("AAPL")

        assert all(isinstance(f, FinancialFact) for f in facts)
        assert all(f.ticker == "AAPL" for f in facts)

        revenue_2025 = next(
            (f for f in facts if f.concept == "Revenue" and f.fiscal_year == 2025),
            None,
        )
        assert revenue_2025 is not None
        assert revenue_2025.value == pytest.approx(416161000000.0)
        assert revenue_2025.statement_type == "income"

        revenue_2024 = next(
            (f for f in facts if f.concept == "Revenue" and f.fiscal_year == 2024),
            None,
        )
        assert revenue_2024 is not None
        assert revenue_2024.value == pytest.approx(391035000000.0)

    def test_get_financial_facts_ticker_not_found_raises(self) -> None:
        """CompanyNotFoundError should be converted to TickerNotFoundError."""
        client = EdgarClient()

        with (
            patch(
                "omninexu.infrastructure.clients.edgar_client.Company",
                side_effect=CompanyNotFoundError("UNKNOWN"),
            ),
            pytest.raises(TickerNotFoundError),
        ):
            client.get_financial_facts("UNKNOWN")

    def test_get_financial_facts_http_error_raises(self) -> None:
        """httpx.HTTPError should be converted to EdgarRateLimitError."""
        client = EdgarClient()

        def raise_http_error(*_args, **_kwargs):
            raise httpx.HTTPError("SEC rate limit")

        with (
            patch(
                "omninexu.infrastructure.clients.edgar_client.Company",
                side_effect=raise_http_error,
            ),
            pytest.raises(EdgarRateLimitError),
        ):
            client.get_financial_facts("AAPL")

    def test_missing_statement_type_skipped(self) -> None:
        """When a 10-K lacks a statement type, it is skipped (not crashed).

        Branch coverage for edgar_client.py:116→110 — ``stmt is None``
        when ``getattr(tenk, attr, None)`` returns None.
        """
        client = EdgarClient()

        income_df = pd.DataFrame({
            "concept": ["us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax"],
            "label": ["Net sales"],
            "2025-09-27 (FY)": [416161000000.0],
            "dimension": [False],
            "is_breakdown": [False],
        })

        # Use a plain class so missing attributes return None from getattr
        class PartialTenk:
            def __init__(self):
                self.income_statement = MagicMock()
                self.income_statement.to_dataframe.return_value = income_df

            def __getattr__(self, name):
                return None

        tenk = PartialTenk()

        filing = MagicMock()
        filing.period_of_report = "2025-09-27"
        filing.accession_no = "ACC"
        filing.filing_date = date(2025, 11, 7)
        filing.obj.return_value = tenk

        filings = MagicMock()
        filings.latest.return_value = filing

        mock_company = MagicMock()
        mock_company.cik = "CIK"
        mock_company.name = "Test"
        mock_company.sic = "SIC"
        mock_company.get_filings.return_value = filings

        with patch("omninexu.infrastructure.clients.edgar_client.Company", return_value=mock_company):
            facts = client.get_financial_facts("AAPL")

        # Should only have income facts, no crash
        assert all(f.statement_type == "income" for f in facts)

    def test_parse_report_date_missing_raises(self) -> None:
        """_parse_report_date should raise when period_of_report is missing."""
        with pytest.raises(ValueError):
            EdgarClient._parse_report_date(None)

