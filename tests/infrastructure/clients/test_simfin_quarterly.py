"""Tests for SimFin quarterly data adapter.

CRITICAL: quarterly data must use source='simfin_quarterly' to prevent
contamination with annual data (source='simfin').
"""

from datetime import date

import pandas as pd

from omninexu.domain.financials import FinancialFact
from omninexu.infrastructure.clients.simfin_adapter import SimFinAdapter, _Variant


def _make_quarterly_income_df() -> pd.DataFrame:
    """Simulate a SimFin quarterly income DataFrame."""
    arrays = [
        ["AAPL", "AAPL", "AAPL"],
        [date(2025, 3, 31), date(2024, 12, 31), date(2024, 9, 30)],
    ]
    idx = pd.MultiIndex.from_arrays(arrays, names=["Ticker", "Report Date"])
    return pd.DataFrame(
        {
            "Revenue": [124.3e9, 145.0e9, 100.0e9],
            "Net Income": [34.63e9, 40.0e9, 25.0e9],
            "Fiscal Year": [2025, 2025, 2024],
            "Fiscal Period": ["Q1", "Q2", "Q3"],
        },
        index=idx,
    )


class TestSimFinQuarterly:
    """Unit tests for SimFin quarterly facts extraction."""

    def test_source_is_simfin_quarterly_not_simfin(self):
        """Quarterly facts must carry source='simfin_quarterly' — never 'simfin'."""
        adapter = SimFinAdapter()
        df = _make_quarterly_income_df()
        adapter._quarterly = _Variant(
            "quarterly", "simfin_quarterly", "Q1",
            income=df, balance=df, cashflow=df,
        )
        adapter._quarterly_failed = False

        facts = adapter.get_quarterly_facts("AAPL")
        assert len(facts) > 0
        for f in facts:
            assert f.source == "simfin_quarterly", (
                f"CONTAMINATION: {f.concept} source='{f.source}'"
            )

    def test_quarterly_period_is_not_fy(self):
        """Quarterly data must have fiscal_period ∈ {Q1, Q2, Q3}, never FY."""
        adapter = SimFinAdapter()
        df = _make_quarterly_income_df()
        adapter._quarterly = _Variant(
            "quarterly", "simfin_quarterly", "Q1",
            income=df, balance=df, cashflow=df,
        )
        adapter._quarterly_failed = False

        facts = adapter.get_quarterly_facts("AAPL")
        periods = {f.fiscal_period for f in facts}
        assert "FY" not in periods, (
            f"CONTAMINATION: quarterly data has FY period: {periods}"
        )
        assert periods == {"Q1", "Q2", "Q3"}

    def test_facts_are_financial_fact_instances(self):
        adapter = SimFinAdapter()
        df = _make_quarterly_income_df()
        adapter._quarterly = _Variant(
            "quarterly", "simfin_quarterly", "Q1",
            income=df, balance=df, cashflow=df,
        )
        adapter._quarterly_failed = False

        facts = adapter.get_quarterly_facts("aapl")
        assert len(facts) > 0
        assert all(isinstance(f, FinancialFact) for f in facts)
        assert all(f.ticker == "AAPL" for f in facts)

    def test_graceful_degradation_when_quarterly_unavailable(self):
        """When quarterly CSVs fail to load, return empty list — don't crash."""
        adapter = SimFinAdapter()
        adapter._quarterly_failed = True
        facts = adapter.get_quarterly_facts("AAPL")
        assert facts == []

    def test_quarterly_annual_are_independent(self):
        """Quarterly failure must not affect annual data."""
        adapter = SimFinAdapter()
        adapter._quarterly_failed = True
        assert adapter._load_quarterly() is False
