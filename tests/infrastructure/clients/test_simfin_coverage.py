"""Coverage supplements for SimFinAdapter — edge cases and bank paths."""

import pandas as pd

from omninexu.infrastructure.clients.simfin_adapter import SimFinAdapter, _Variant


def _make_income_df(ticker: str = "AAPL") -> pd.DataFrame:
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


class TestSimFinCoverage:
    """Additional tests for SimFinAdapter edge-case branches."""

    # ── _extract_rows edge cases ──────────────────────────────────────

    def test_extract_rows_missing_column_returns_empty(self):
        """col not in subset.columns → [ ]"""
        adapter = SimFinAdapter()
        income_df = _make_income_df("AAPL")
        v = _Variant("annual", "simfin", "FY", income=income_df)
        rows = adapter._extract_rows(
            "AAPL", "NonExistentCol", "income", is_bank=False, v=v,
        )
        assert rows == []

    def test_extract_rows_skips_nan_values(self):
        """NaN values in concept column are skipped."""
        data = {
            "Ticker": ["AAPL", "AAPL"],
            "Fiscal Year": [2022, 2023],
            "Fiscal Period": ["FY", "FY"],
            "Revenue": [3.65e11, float("nan")],
        }
        df = pd.DataFrame(data)
        df["Report Date"] = pd.to_datetime(["2022-09-30", "2023-09-30"])
        df = df.set_index(["Ticker", "Report Date"])

        adapter = SimFinAdapter()
        adapter._annual = _Variant("annual", "simfin", "FY", income=df)
        adapter._loaded = True

        facts = adapter.get_financial_facts("AAPL")
        revenue = [f for f in facts if f.concept == "Revenue"]
        assert len(revenue) == 1  # NaN row skipped

    # ── Bank path ─────────────────────────────────────────────────────

    def test_bank_ticker_uses_bank_map(self):
        """JPM (a bank) gets _BANK_MAP → no GrossProfit."""
        data = {
            "Ticker": ["JPM"],
            "Fiscal Year": [2024],
            "Fiscal Period": ["FY"],
            "Revenue": [1.5e11],
            "Net Income": [5e10],
            "Total Assets": [3.9e12],
            "Total Liabilities": [3.6e12],
            "Total Equity": [3e11],
            "Net Cash from Operating Activities": [2e10],
        }
        df = pd.DataFrame(data)
        df["Report Date"] = pd.to_datetime(["2024-12-31"])
        df = df.set_index(["Ticker", "Report Date"])

        adapter = SimFinAdapter()
        adapter._annual = _Variant(
            "annual", "simfin", "FY",
            income_banks=df, balance_banks=df, cashflow_banks=df,
        )
        adapter._loaded = True

        facts = adapter.get_financial_facts("JPM")
        concepts = {f.concept for f in facts}
        assert "GrossProfit" not in concepts
        assert "Revenue" in concepts

    # ── get_company_info ──────────────────────────────────────────────

    def test_get_company_info_found(self):
        from unittest.mock import patch

        import simfin as sf

        adapter = SimFinAdapter()
        companies_df = pd.DataFrame(
            {"CIK": ["0000320193"], "Company Name": ["Apple Inc."],
             "IndustryId": ["3571"]},
            index=pd.Index(["AAPL"], name="Ticker"),
        )
        with patch.object(sf, "set_data_dir"), \
             patch.object(sf, "load_companies", return_value=companies_df):
            info = adapter.get_company_info("AAPL")
        assert info["ticker"] == "AAPL"
        assert info["cik"] == "0000320193"

    def test_get_company_info_not_found(self):
        from unittest.mock import patch

        import simfin as sf

        adapter = SimFinAdapter()
        empty_df = pd.DataFrame(
            {"CIK": [], "Company Name": [], "IndustryId": []},
            index=pd.Index([], name="Ticker"),
        )
        with patch.object(sf, "set_data_dir"), \
             patch.object(sf, "load_companies", return_value=empty_df):
            info = adapter.get_company_info("UNKNOWN")
        assert info["cik"] == ""

    # ── _load ─────────────────────────────────────────────────────────

    def test_load_fetches_six_dataframes(self):
        from unittest.mock import patch

        import simfin as sf

        adapter = SimFinAdapter(data_dir="/fake/simfin")
        assert not adapter._loaded

        with patch.object(sf, "set_data_dir") as mock_set, \
             patch.object(sf, "load_income", return_value=_make_income_df()) as li, \
             patch.object(sf, "load_balance", return_value=pd.DataFrame()) as lb, \
             patch.object(sf, "load_cashflow", return_value=pd.DataFrame()) as lc, \
             patch.object(sf, "load_income_banks", return_value=pd.DataFrame()) as lib, \
             patch.object(sf, "load_balance_banks", return_value=pd.DataFrame()) as lbb, \
             patch.object(sf, "load_cashflow_banks", return_value=pd.DataFrame()) as lcb:
            adapter._load()

        assert adapter._loaded
        assert adapter._annual.income is not None
        mock_set.assert_called_once_with("/fake/simfin")
        li.assert_called_once_with(variant="annual", market="us")
        lb.assert_called_once_with(variant="annual", market="us")
        lc.assert_called_once_with(variant="annual", market="us")
        lib.assert_called_once_with(variant="annual", market="us")
        lbb.assert_called_once_with(variant="annual", market="us")
        lcb.assert_called_once_with(variant="annual", market="us")
