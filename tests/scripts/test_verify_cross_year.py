"""Tests for cross-year consistency verification (Level 2)."""

from datetime import date

from omninexu.domain.financials import FinancialFact
from scripts.verify.verify_financials import verify_cross_year


def test_cross_year_passes_with_matching_values():
    """Same (year, concept) from two filings → PASS when within tolerance."""
    class FakeClient:
        def get_financial_facts(self, ticker: str, num_filings: int = 1) -> list[FinancialFact]:
            return [
                FinancialFact(
                    ticker="AAPL", fiscal_year=2024, fiscal_period="FY",
                    report_date=date(2025, 9, 27), concept="Revenue",
                    value=391_035_000_000.0, source_filing="10-K-2025",
                ),
                FinancialFact(
                    ticker="AAPL", fiscal_year=2024, fiscal_period="FY",
                    report_date=date(2024, 9, 28), concept="Revenue",
                    value=391_035_000_000.0, source_filing="10-K-2024",
                ),
            ]

    result = verify_cross_year("AAPL", client=FakeClient())
    assert result["failures"] == 0
    assert any("PASS" in m for m in result["messages"])


def test_cross_year_flags_significant_deviation():
    """Large difference between overlapping filings → FAIL."""
    class FakeClient:
        def get_financial_facts(self, ticker: str, num_filings: int = 1) -> list[FinancialFact]:
            return [
                FinancialFact(
                    ticker="AAPL", fiscal_year=2024, fiscal_period="FY",
                    report_date=date(2025, 9, 27), concept="Revenue",
                    value=400_000_000_000.0, source_filing="10-K-2025",
                ),
                FinancialFact(
                    ticker="AAPL", fiscal_year=2024, fiscal_period="FY",
                    report_date=date(2024, 9, 28), concept="Revenue",
                    value=391_000_000_000.0, source_filing="10-K-2024",
                ),
            ]

    result = verify_cross_year("AAPL", client=FakeClient())
    assert result["failures"] == 1
    assert any("FAIL" in m for m in result["messages"])


def test_cross_year_skips_non_overlapping_years():
    """Facts from different fiscal years → no comparison triggered."""
    class FakeClient:
        def get_financial_facts(self, ticker: str, num_filings: int = 1) -> list[FinancialFact]:
            return [
                FinancialFact(
                    ticker="AAPL", fiscal_year=2025, fiscal_period="FY",
                    report_date=date(2025, 9, 27), concept="Revenue",
                    value=416_161_000_000.0, source_filing="10-K-2025",
                ),
                FinancialFact(
                    ticker="AAPL", fiscal_year=2024, fiscal_period="FY",
                    report_date=date(2024, 9, 28), concept="Revenue",
                    value=391_035_000_000.0, source_filing="10-K-2024",
                ),
            ]

    result = verify_cross_year("AAPL", client=FakeClient())
    assert result["failures"] == 0
    assert result["messages"] == []
