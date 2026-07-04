"""Tests for scripts/ingest/import_gics.py."""

from unittest.mock import MagicMock, patch

from omninexu.infrastructure.gics_mapping import GicsClassification


class _FakeCompany:
    def __init__(self, ticker="AAPL", sic_code="3571"):
        self.ticker = ticker
        self.industry = MagicMock()
        self.industry.sic_code = sic_code


class TestImportGics:
    def test_import_maps_sic_to_gics(self):
        from scripts.ingest.import_gics import import_gics

        with (
            patch("scripts.ingest.import_gics.SessionLocal"),
            patch("scripts.ingest.import_gics.load_mapping"),
            patch("scripts.ingest.import_gics.lookup") as mock_lookup,
            patch("scripts.ingest.import_gics.CompanyRepository") as mock_repo_cls,
        ):
            gics = GicsClassification(
                sic="3571",
                gics_sector="Information Technology",
                gics_sub_industry="Technology Hardware, Storage & Peripherals",
            )
            mock_lookup.return_value = gics
            mock_repo = mock_repo_cls.return_value
            mock_repo.get_by_ticker.return_value = _FakeCompany("AAPL", "3571")

            results = import_gics(["AAPL"])
            assert results["AAPL"] == gics.gics_sub_industry
            mock_repo.update_gics.assert_called_once_with("AAPL", gics)

    def test_import_company_not_found(self):
        from scripts.ingest.import_gics import import_gics

        with (
            patch("scripts.ingest.import_gics.SessionLocal"),
            patch("scripts.ingest.import_gics.load_mapping"),
            patch("scripts.ingest.import_gics.lookup"),
            patch("scripts.ingest.import_gics.CompanyRepository") as mock_repo_cls,
        ):
            mock_repo = mock_repo_cls.return_value
            mock_repo.get_by_ticker.return_value = None

            results = import_gics(["ZZZZ"])
            assert results["ZZZZ"] == "NOT FOUND"

    def test_import_no_sic_code(self):
        from scripts.ingest.import_gics import import_gics

        with (
            patch("scripts.ingest.import_gics.SessionLocal"),
            patch("scripts.ingest.import_gics.load_mapping"),
            patch("scripts.ingest.import_gics.lookup"),
            patch("scripts.ingest.import_gics.CompanyRepository") as mock_repo_cls,
        ):
            mock_repo = mock_repo_cls.return_value
            mock_repo.get_by_ticker.return_value = _FakeCompany("AAPL", None)

            results = import_gics(["AAPL"])
            assert results["AAPL"] == "NO SIC"

    def test_import_no_gics_mapping(self):
        from scripts.ingest.import_gics import import_gics

        with (
            patch("scripts.ingest.import_gics.SessionLocal"),
            patch("scripts.ingest.import_gics.load_mapping"),
            patch("scripts.ingest.import_gics.lookup") as mock_lookup,
            patch("scripts.ingest.import_gics.CompanyRepository") as mock_repo_cls,
        ):
            mock_lookup.return_value = None
            mock_repo = mock_repo_cls.return_value
            mock_repo.get_by_ticker.return_value = _FakeCompany("AAPL", "9999")

            results = import_gics(["AAPL"])
            assert results["AAPL"] == "NO MAPPING"

    def test_import_default_tickers(self):
        from scripts.ingest.import_gics import import_gics

        with (
            patch("scripts.ingest.import_gics.SessionLocal"),
            patch("scripts.ingest.import_gics.load_mapping"),
            patch("scripts.ingest.import_gics.lookup") as mock_lookup,
            patch("scripts.ingest.import_gics.CompanyRepository") as mock_repo_cls,
        ):
            gics = GicsClassification(
                sic="3571",
                gics_sector="IT",
                gics_sub_industry="Hardware",
            )
            mock_lookup.return_value = gics
            mock_repo = mock_repo_cls.return_value
            mock_repo.get_by_ticker.return_value = _FakeCompany()

            results = import_gics()
            assert len(results) == 3  # default tickers: AAPL, MSFT, NVDA
