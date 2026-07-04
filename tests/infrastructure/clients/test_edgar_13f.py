"""Tests for 13F institutional holdings download."""

from unittest.mock import MagicMock, patch

from omninexu.infrastructure.clients.edgar_13f import (
    MAJOR_INSTITUTIONS,
    _safe_float,
    get_13f_holdings,
)


class TestSafeFloat:
    def test_valid_float(self):
        assert _safe_float(1000.5) == 1000.5

    def test_none_returns_none(self):
        assert _safe_float(None) is None

    def test_string_returns_float(self):
        assert _safe_float("2000") == 2000.0

    def test_invalid_returns_none(self):
        assert _safe_float("N/A") is None


class TestGet13FHoldings:
    """Unit tests with mocked edgartools get_filings."""

    def _make_filing_mock(self, has_ticker: bool = True):
        """Build a mock 13F filing with AAPL holdings."""
        import pandas as pd

        data = {"Ticker": ["AAPL"], "SharesPrnAmount": [1.3e9],
                "Value": [3.2e11], "Cusip": ["037833100"]}
        if not has_ticker:
            data = {"Ticker": ["MSFT"], "SharesPrnAmount": [1e9],
                    "Value": [2e11], "Cusip": ["594918104"]}

        filing = MagicMock()
        filing.accession_no = "0000102909-25-000001"
        filing.period_of_report = "2025-03-31"

        obj = MagicMock()
        obj.holdings = pd.DataFrame(data)
        filing.obj.return_value = obj

        return filing

    def test_returns_holdings_for_ticker(self):
        filing = self._make_filing_mock(has_ticker=True)

        with patch("omninexu.infrastructure.clients.edgar_13f.Company") as mock_co:
            mock_co.return_value.get_filings.return_value.latest.return_value = filing
            results = get_13f_holdings("AAPL")

        assert len(results) > 0
        assert results[0]["holder_name"] == "Vanguard Group"
        assert results[0]["value"] == 3.2e11

    def test_skips_institution_without_ticker(self):
        filing = self._make_filing_mock(has_ticker=False)

        with patch("omninexu.infrastructure.clients.edgar_13f.Company") as mock_co:
            mock_co.return_value.get_filings.return_value.latest.return_value = filing
            results = get_13f_holdings("AAPL")

        assert len(results) == 0  # MSFT match only, AAPL not found

    def test_resilient_to_filing_failure(self):
        """One institution's filing failing → other institutions still processed."""
        good = self._make_filing_mock(has_ticker=True)
        co_mock = MagicMock()
        co_mock.get_filings.return_value.latest.return_value = good

        with patch("omninexu.infrastructure.clients.edgar_13f.Company") as mock_co:
            mock_co.side_effect = [RuntimeError("Network error"), co_mock]
            with patch("omninexu.infrastructure.clients.edgar_13f.MAJOR_INSTITUTIONS",
                       [("Vanguard", "CIK1"), ("BlackRock", "CIK2")]):
                results = get_13f_holdings("AAPL")

        assert len(results) == 1  # BlackRock succeeded

    def test_major_institutions_has_ten_entries(self):
        assert len(MAJOR_INSTITUTIONS) == 10
