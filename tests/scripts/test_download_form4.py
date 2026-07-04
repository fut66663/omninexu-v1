"""Tests for scripts/ingest/download_form4.py."""

from datetime import date
from unittest.mock import patch


class TestParseDate:
    def test_parse_valid_iso_date(self):
        from scripts.ingest.download_form4 import _parse_date
        assert _parse_date("2025-06-15") == date(2025, 6, 15)

    def test_parse_none_returns_none(self):
        from scripts.ingest.download_form4 import _parse_date
        assert _parse_date(None) is None

    def test_parse_empty_string_returns_none(self):
        from scripts.ingest.download_form4 import _parse_date
        assert _parse_date("") is None

    def test_parse_invalid_date_returns_none(self):
        from scripts.ingest.download_form4 import _parse_date
        assert _parse_date("garbage") is None


class TestDownloadForm4:
    def test_download_saves_trades(self):
        from scripts.ingest.download_form4 import download_form4

        with (
            patch("scripts.ingest.download_form4.SessionLocal"),
            patch("scripts.ingest.download_form4.InsiderRepository") as mock_repo_cls,
            patch("scripts.ingest.download_form4.get_insider_trades") as mock_get,
        ):
            mock_repo = mock_repo_cls.return_value
            mock_get.return_value = [
                {
                    "insider_name": "Tim Cook",
                    "insider_title": "CEO",
                    "transaction_type": "S",
                    "shares": 100_000,
                    "price": 175.50,
                    "transaction_date": "2025-06-15",
                    "source_filing": "https://...",
                },
            ]

            results = download_form4(["AAPL"])
            assert results["AAPL"] == 1
            mock_repo.save_trades.assert_called_once()

    def test_download_skips_missing_date(self):
        from scripts.ingest.download_form4 import download_form4

        with (
            patch("scripts.ingest.download_form4.SessionLocal"),
            patch("scripts.ingest.download_form4.InsiderRepository"),
            patch("scripts.ingest.download_form4.get_insider_trades") as mock_get,
        ):
            mock_get.return_value = [
                {
                    "insider_name": "Tim Cook",
                    "insider_title": "CEO",
                    "transaction_type": "S",
                    "shares": 100_000,
                    "price": 175.50,
                    "transaction_date": None,  # no date — should be skipped
                    "source_filing": "https://...",
                },
            ]

            results = download_form4(["AAPL"])
            assert results["AAPL"] == 0  # trade skipped

    def test_download_handles_failure(self):
        from scripts.ingest.download_form4 import download_form4

        with (
            patch("scripts.ingest.download_form4.SessionLocal"),
            patch("scripts.ingest.download_form4.InsiderRepository"),
            patch("scripts.ingest.download_form4.get_insider_trades") as mock_get,
        ):
            mock_get.side_effect = RuntimeError("SEC unavailable")

            results = download_form4(["AAPL"])
            assert results["AAPL"] == -1

    def test_download_default_tickers(self):
        from scripts.ingest.download_form4 import download_form4

        with (
            patch("scripts.ingest.download_form4.SessionLocal"),
            patch("scripts.ingest.download_form4.InsiderRepository"),
            patch("scripts.ingest.download_form4.get_insider_trades") as mock_get,
        ):
            mock_get.return_value = []
            results = download_form4()
            assert len(results) >= 10
