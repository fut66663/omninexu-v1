"""Tests for data verification scripts."""

from datetime import date

from omninexu.domain.financials import FinancialFact
from scripts.verify.verify_financials import (
    _check_fact,
    _find_fact,
    verify_ticker,
)


def _make_aapl_facts() -> list[FinancialFact]:
    """Return a list of AAPL-like facts for testing."""
    return [
        FinancialFact(
            ticker="AAPL",
            fiscal_year=2025,
            fiscal_period="FY",
            report_date=date(2025, 9, 27),
            concept="Revenue",
            value=416_161_000_000.0,
            unit="USD",
            source_filing="10-K",
            statement_type="income",
        ),
        FinancialFact(
            ticker="AAPL",
            fiscal_year=2025,
            fiscal_period="FY",
            report_date=date(2025, 9, 27),
            concept="NetIncome",
            value=112_010_000_000.0,
            unit="USD",
            source_filing="10-K",
            statement_type="income",
        ),
    ]


class TestVerifyFinancials:
    """Tests for scripts/verify_financials.py logic."""

    def _make_facts(self) -> list[FinancialFact]:
        """Return a list of AAPL-like facts for testing."""
        return _make_aapl_facts()

    def test_find_fact_returns_latest_year(self):
        """_find_fact should return the most recent fiscal year match."""
        facts = self._make_facts()
        facts.append(
            FinancialFact(
                ticker="AAPL",
                fiscal_year=2024,
                fiscal_period="FY",
                report_date=date(2024, 9, 28),
                concept="Revenue",
                value=391_035_000_000.0,
                unit="USD",
                source_filing="10-K",
                statement_type="income",
            )
        )

        result = _find_fact(facts, "Revenue")
        assert result is not None
        assert result.fiscal_year == 2025

    def test_find_fact_missing_returns_none(self):
        """_find_fact should return None when concept is missing."""
        facts = self._make_facts()
        assert _find_fact(facts, "OperatingCashFlow") is None

    def test_check_fact_passes_within_tolerance(self):
        """_check_fact should return True when value is within tolerance."""
        fact = FinancialFact(
            ticker="AAPL",
            fiscal_year=2025,
            fiscal_period="FY",
            report_date=date(2025, 9, 27),
            concept="Revenue",
            value=416_161_000_000.0,
            unit="USD",
        )
        passed, message = _check_fact(fact, 416_161_000_000, "Revenue")
        assert passed is True
        assert "PASS" in message

    def test_check_fact_fails_outside_tolerance(self):
        """_check_fact should return False when value is outside tolerance."""
        fact = FinancialFact(
            ticker="AAPL",
            fiscal_year=2025,
            fiscal_period="FY",
            report_date=date(2025, 9, 27),
            concept="Revenue",
            value=400_000_000_000.0,
            unit="USD",
        )
        passed, message = _check_fact(fact, 416_161_000_000, "Revenue")
        assert passed is False
        assert "FAIL" in message

    def test_check_fact_missing_returns_fail(self):
        """_check_fact should return False when fact is None."""
        passed, message = _check_fact(None, 416_161_000_000, "Revenue")
        assert passed is False
        assert "MISSING" in message

    def test_verify_ticker_passes_with_expected_values(self):
        """verify_ticker should return 0 failures for accurate facts."""
        class FakeClient:
            def get_financial_facts(self, ticker: str) -> list[FinancialFact]:
                return _make_aapl_facts()

        result = verify_ticker("AAPL", client=FakeClient())
        assert result["failures"] == 0
        assert all("PASS" in m for m in result["messages"])

    def test_verify_ticker_skips_unconfigured_year(self):
        """verify_ticker should SKIP, not FAIL, when expected value is unconfigured."""
        class FakeClient:
            def get_financial_facts(self, ticker: str) -> list[FinancialFact]:
                return [
                    FinancialFact(
                        ticker="AAPL",
                        fiscal_year=2099,
                        fiscal_period="FY",
                        report_date=date(2099, 9, 27),
                        concept=concept,
                        value=416_161_000_000.0,
                        unit="USD",
                    )
                    for concept in ("Revenue", "NetIncome")
                ]

        result = verify_ticker("AAPL", client=FakeClient())
        assert result["failures"] == 0
        assert all("SKIP" in m for m in result["messages"])

    def test_verify_ticker_fails_when_value_inaccurate(self):
        """verify_ticker should count inaccurate values as failures."""
        class FakeClient:
            def get_financial_facts(self, ticker: str) -> list[FinancialFact]:
                return [
                    FinancialFact(
                        ticker="AAPL",
                        fiscal_year=2025,
                        fiscal_period="FY",
                        report_date=date(2025, 9, 27),
                        concept="Revenue",
                        value=1.0,
                        unit="USD",
                    ),
                    FinancialFact(
                        ticker="AAPL",
                        fiscal_year=2025,
                        fiscal_period="FY",
                        report_date=date(2025, 9, 27),
                        concept="NetIncome",
                        value=112_010_000_000.0,
                        unit="USD",
                    ),
                ]

        result = verify_ticker("AAPL", client=FakeClient())
        assert result["failures"] == 1
        assert any("FAIL" in m for m in result["messages"])
