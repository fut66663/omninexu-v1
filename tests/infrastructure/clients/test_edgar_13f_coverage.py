"""Coverage supplements for edgar_13f.py — filing=None, parse failure, empty holdings."""

from unittest.mock import MagicMock, patch

import pandas as pd

from omninexu.infrastructure.clients.edgar_13f import get_13f_holdings


class TestEdgar13fCoverage:
    """Edge cases not covered by existing 13F tests."""

    def test_filing_is_none_skipped(self):
        """When latest() returns None, the institution is skipped."""
        with patch("omninexu.infrastructure.clients.edgar_13f.Company") as mock_co, \
             patch("omninexu.infrastructure.clients.edgar_13f.MAJOR_INSTITUTIONS",
                   [("NoFilingCo", "CIK1")]):
            mock_co.return_value.get_filings.return_value.latest.return_value = None
            results = get_13f_holdings("AAPL")
        assert results == []

    def test_filing_obj_parse_failure_skipped(self):
        """When filing.obj() raises, the institution is skipped."""
        with patch("omninexu.infrastructure.clients.edgar_13f.Company") as mock_co, \
             patch("omninexu.infrastructure.clients.edgar_13f.MAJOR_INSTITUTIONS",
                   [("BadParse", "CIK1")]):
            filing = MagicMock()
            filing.period_of_report = "2025-03-31"
            filing.obj.side_effect = RuntimeError("parse error")
            mock_co.return_value.get_filings.return_value.latest.return_value = filing
            results = get_13f_holdings("AAPL")
        assert results == []

    def test_empty_period_of_report_skips_date_parsing(self):
        """When ``period_of_report`` is empty, date parsing is skipped.

        Branch coverage for edgar_13f.py:61→69 — ``report_date_str`` is
        falsy so the if-body is bypassed entirely.
        """
        with patch("omninexu.infrastructure.clients.edgar_13f.Company") as mock_co, \
             patch("omninexu.infrastructure.clients.edgar_13f.MAJOR_INSTITUTIONS",
                   [("EmptyDate", "CIK1")]):
            filing = MagicMock()
            filing.accession_no = "ACC-001"
            filing.period_of_report = ""  # empty — branch target
            obj = MagicMock()
            obj.holdings = pd.DataFrame({
                "Ticker": ["AAPL"], "SharesPrnAmount": [1e6],
                "Value": [1e8], "Cusip": ["037833100"],
            })
            filing.obj.return_value = obj
            mock_co.return_value.get_filings.return_value.latest.return_value = filing
            results = get_13f_holdings("AAPL")
        assert len(results) == 1
        assert results[0]["holder_name"] == "EmptyDate"

    def test_none_period_of_report_skipped(self):
        """When ``period_of_report`` is None, date branch is skipped."""
        with patch("omninexu.infrastructure.clients.edgar_13f.Company") as mock_co, \
             patch("omninexu.infrastructure.clients.edgar_13f.MAJOR_INSTITUTIONS",
                   [("NoneDate", "CIK1")]):
            filing = MagicMock()
            filing.accession_no = "ACC-001"
            filing.period_of_report = None  # None goes through `or ""` → ""
            obj = MagicMock()
            obj.holdings = pd.DataFrame({
                "Ticker": ["AAPL"], "SharesPrnAmount": [1e6],
                "Value": [1e8], "Cusip": ["037833100"],
            })
            filing.obj.return_value = obj
            mock_co.return_value.get_filings.return_value.latest.return_value = filing
            results = get_13f_holdings("AAPL")
        assert len(results) == 1

    def test_empty_holdings_skipped(self):
        """When holdings DataFrame is empty, the institution is skipped."""
        with patch("omninexu.infrastructure.clients.edgar_13f.Company") as mock_co, \
             patch("omninexu.infrastructure.clients.edgar_13f.MAJOR_INSTITUTIONS",
                   [("EmptyHolder", "CIK1")]):
            filing = MagicMock()
            filing.accession_no = "ACC-001"
            filing.period_of_report = "2025-03-31"
            obj = MagicMock()
            obj.holdings = pd.DataFrame()
            filing.obj.return_value = obj
            mock_co.return_value.get_filings.return_value.latest.return_value = filing
            results = get_13f_holdings("AAPL")
        assert results == []
