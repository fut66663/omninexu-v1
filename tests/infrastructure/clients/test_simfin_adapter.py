"""Tests for SimFinAdapter."""

import pandas as pd

from omninexu.infrastructure.clients.simfin_adapter import (
    _BANKS,
    SimFinAdapter,
    _Variant,
)


def _make_income_df(ticker: str = "AAPL") -> pd.DataFrame:
    """Build a minimal SimFin income DataFrame for testing."""
    data = {
        "Ticker": [ticker, ticker, ticker],
        "Fiscal Year": [2022, 2023, 2024],
        "Fiscal Period": ["FY", "FY", "FY"],
        "Revenue": [3.65e11, 3.83e11, 3.91e11],
        "Net Income": [9.47e10, 9.70e10, 9.37e10],
        "Gross Profit": [1.53e11, 1.69e11, 1.81e11],
        "Operating Income (Loss)": [1.09e11, 1.14e11, 1.23e11],
    }
    df = pd.DataFrame(data)
    df["Report Date"] = pd.to_datetime([f"{y}-09-30" for y in range(2022, 2025)])
    return df.set_index(["Ticker", "Report Date"])


class TestSimFinAdapter:
    """Unit tests for SimFinAdapter."""

    def test_bank_set_includes_jpm(self):
        assert "JPM" in _BANKS

    def test_bank_set_excludes_aapl(self):
        assert "AAPL" not in _BANKS

    def test_ticker_googl_to_goog(self):
        assert SimFinAdapter._ticker_simfin("GOOGL") == "GOOG"
        assert SimFinAdapter._ticker_simfin("AAPL") == "AAPL"

    def test_get_financial_facts_from_mock_df(self):
        adapter = SimFinAdapter()
        income_df = _make_income_df("AAPL")
        adapter._annual = _Variant(
            "annual", "simfin", "FY", income=income_df,
        )
        adapter._loaded = True

        facts = adapter.get_financial_facts("AAPL")
        # 4 concepts × 3 years = 12 facts
        assert len(facts) == 12
        revenue_facts = [f for f in facts if f.concept == "Revenue"]
        assert len(revenue_facts) == 3
        assert all(f.source_filing == "simfin" for f in facts)

    def test_get_financial_facts_respects_start_year(self):
        adapter = SimFinAdapter()
        adapter._annual = _Variant(
            "annual", "simfin", "FY", income=_make_income_df("AAPL"),
        )
        adapter._loaded = True

        facts = adapter.get_financial_facts("AAPL", start_year=2024)
        revenue_facts = [f for f in facts if f.concept == "Revenue"]
        assert len(revenue_facts) == 1
        assert revenue_facts[0].fiscal_year == 2024
