"""Tests for Form 4 insider transactions download."""

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd

from omninexu.infrastructure.clients.edgar_form4 import (
    _parse_date,
    _safe_float,
    get_insider_trades,
)


class TestSafeFloat:
    def test_valid(self):
        assert _safe_float(500.0) == 500.0

    def test_none(self):
        assert _safe_float(None) is None


class TestGetInsiderTrades:
    """Unit tests with mocked edgartools Company().get_filings()."""

    @staticmethod
    def _make_df(rows: list[dict]) -> pd.DataFrame:
        return pd.DataFrame(rows)

    @staticmethod
    def _make_filing(accession: str, df: pd.DataFrame | None = None) -> MagicMock:
        if df is None:
            df = pd.DataFrame({"Code": [], "Insider": [], "Position": [],
                               "Shares": [], "Price": [], "Date": []})
        obj = MagicMock()
        obj.to_dataframe.return_value = df
        f = MagicMock()
        f.accession_no = accession
        f.filing_date = pd.Timestamp("2025-06-15").date()
        f.text.return_value = "<html>Form 4</html>"
        f.obj.return_value = obj
        return f

    def test_returns_p_and_s_only(self):
        df = self._make_df([
            {"Code": "S", "Insider": "Tim Cook", "Position": "CEO",
             "Shares": 10000.0, "Price": 195.0, "Date": pd.Timestamp("2025-06-15")},
            {"Code": "P", "Insider": "Arthur Levinson", "Position": "Chair",
             "Shares": 5000.0, "Price": 190.0, "Date": pd.Timestamp("2025-06-10")},
            {"Code": "M", "Insider": "Someone", "Position": "Officer",
             "Shares": 20000.0, "Price": None, "Date": pd.Timestamp("2025-06-01")},
        ])
        filing = self._make_filing("ACC-001", df)

        with patch("omninexu.infrastructure.clients.edgar_form4.Company") as mock_co:
            mock_co.return_value.get_filings.return_value.latest.return_value = [filing]
            results = get_insider_trades("AAPL")

        assert len(results) == 2
        types = {r["transaction_type"] for r in results}
        assert types == {"P", "S"}

    def test_deduplicates_amended(self):
        df = self._make_df([
            {"Code": "S", "Insider": "Seller", "Position": "",
             "Shares": 5000.0, "Price": 100.0, "Date": pd.Timestamp("2025-06-01")},
        ])

        with patch("omninexu.infrastructure.clients.edgar_form4.Company") as mock_co:
            mock_co.return_value.get_filings.return_value.latest.return_value = [
                self._make_filing("ACC-001", df),
                self._make_filing("ACC-001", df),  # same accession
            ]
            results = get_insider_trades("AAPL")

        assert len(results) == 1

    def test_empty_dataframe(self):
        with patch("omninexu.infrastructure.clients.edgar_form4.Company") as mock_co:
            mock_co.return_value.get_filings.return_value.latest.return_value = [
                self._make_filing("ACC-001"),
            ]
            results = get_insider_trades("AAPL")

        assert results == []

    def test_resilient_to_parse_failure(self):
        bad = MagicMock()
        bad.accession_no = "BAD"
        bad.obj.side_effect = RuntimeError("corrupt")

        df = self._make_df([
            {"Code": "S", "Insider": "A", "Position": "",
             "Shares": 1000.0, "Price": 1.0, "Date": pd.Timestamp("2025-01-01")},
        ])

        with patch("omninexu.infrastructure.clients.edgar_form4.Company") as mock_co:
            mock_co.return_value.get_filings.return_value.latest.return_value = [
                bad, self._make_filing("ACC-002", df),
            ]
            results = get_insider_trades("AAPL")

        assert len(results) == 1


class TestParseDate:
    """Tests for _parse_date() error handling (lines 88-89)."""

    def test_parse_date_none_returns_none(self):
        assert _parse_date(None) is None

    def test_parse_date_valid_iso_string(self):
        assert _parse_date("2025-06-15") == "2025-06-15"

    def test_parse_date_timestamp_object(self):
        ts = pd.Timestamp("2025-06-15")
        assert _parse_date(ts) == "2025-06-15"

    def test_parse_date_date_object(self):
        d = date(2025, 6, 15)
        assert _parse_date(d) == "2025-06-15"

    def test_parse_date_unparseable_returns_none(self):
        """An object where both isinstance checks fail and str() raises TypeError → None."""
        # Create an object that raises TypeError on str() call.
        class Unstrable:
            def __str__(self):
                raise TypeError("cannot stringify")

        assert _parse_date(Unstrable()) is None

    def test_safe_float_invalid_type_returns_none(self):
        """A non-numeric string that raises ValueError should return None."""
        assert _safe_float("not_a_number") is None

    def test_safe_float_invalid_type_raises_typeerror_covered(self):
        """An object that cannot be converted to float should return None."""
        obj = object()
        assert _safe_float(obj) is None
