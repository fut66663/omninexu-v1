"""Tests for scripts/ingest/download_13f.py."""

from datetime import date
from unittest.mock import patch


class TestParseDate:
    def test_parse_valid_iso_date(self):
        from scripts.ingest.download_13f import _parse_date
        result = _parse_date("2025-03-31")
        assert result == date(2025, 3, 31)

    def test_parse_none_returns_none(self):
        from scripts.ingest.download_13f import _parse_date
        assert _parse_date(None) is None

    def test_parse_empty_string_returns_none(self):
        from scripts.ingest.download_13f import _parse_date
        assert _parse_date("") is None

    def test_parse_invalid_date_returns_none(self):
        from scripts.ingest.download_13f import _parse_date
        assert _parse_date("not-a-date") is None


class TestDownload13f:
    def test_download_saves_holdings(self):
        from scripts.ingest.download_13f import download_13f

        with (
            patch("scripts.ingest.download_13f.SessionLocal"),
            patch("scripts.ingest.download_13f.InstitutionalRepository") as mock_repo_cls,
            patch("scripts.ingest.download_13f.get_13f_holdings") as mock_get,
        ):
            mock_repo = mock_repo_cls.return_value
            mock_get.return_value = [
                {
                    "holder_name": "Vanguard Group",
                    "shares": 1_000_000,
                    "value": 150_000_000_000,
                    "cusip": "037833100",
                    "report_date": "2025-03-31",
                    "source_filing": "https://...",
                },
            ]

            results = download_13f(["AAPL"])
            assert results["AAPL"] == 1
            mock_repo.save_holdings.assert_called_once()

    def test_download_handles_failure(self):
        from scripts.ingest.download_13f import download_13f

        with (
            patch("scripts.ingest.download_13f.SessionLocal"),
            patch("scripts.ingest.download_13f.InstitutionalRepository"),
            patch("scripts.ingest.download_13f.get_13f_holdings") as mock_get,
        ):
            mock_get.side_effect = RuntimeError("SEC rate limit")

            results = download_13f(["AAPL"])
            assert results["AAPL"] == -1

    def test_download_default_tickers(self):
        from scripts.ingest.download_13f import download_13f

        with (
            patch("scripts.ingest.download_13f.SessionLocal"),
            patch("scripts.ingest.download_13f.InstitutionalRepository"),
            patch("scripts.ingest.download_13f.get_13f_holdings") as mock_get,
        ):
            mock_get.return_value = []
            results = download_13f()
            assert len(results) >= 10  # default tickers
