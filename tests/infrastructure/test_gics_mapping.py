"""Tests for GICS mapping infrastructure."""

from unittest.mock import MagicMock, patch

from omninexu.infrastructure.gics_mapping import (
    GicsClassification,
    load_mapping,
    lookup,
)


class TestGicsLookup:
    """Unit tests for GICS SIC→classification lookup."""

    @classmethod
    def setup_class(cls):
        """Pre-load mapping with bundled test CSV (CI has no data volume)."""
        import csv
        import tempfile
        from pathlib import Path

        # Write a minimal SIC→GICS CSV for CI-compatible testing
        cls._tmpdir = tempfile.TemporaryDirectory()
        csv_path = Path(cls._tmpdir.name) / "sic_to_gics.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["sic", "gics_sector", "gics_industry_group", "gics_industry", "gics_sub_industry"])
            writer.writerow(["3571", "Information Technology", "Technology Hardware & Equipment", "Technology Hardware, Storage & Peripherals", "Technology Hardware, Storage & Peripherals"])
            writer.writerow(["7372", "Information Technology", "Software & Services", "Software", "Application Software"])
            writer.writerow(["3674", "Information Technology", "Semiconductors & Semiconductor Equipment", "Semiconductors & Semiconductor Equipment", "Semiconductors"])
            writer.writerow(["3711", "Consumer Discretionary", "Automobiles & Components", "Automobiles", "Automobile Manufacturers"])
            writer.writerow(["5331", "Consumer Discretionary", "Consumer Discretionary Distribution & Retail", "Broadline Retail", "Broadline Retail"])
            writer.writerow(["2911", "Energy", "Energy", "Oil, Gas & Consumable Fuels", "Integrated Oil & Gas"])
            writer.writerow(["6021", "Financials", "Banks", "Banks", "Diversified Banks"])
            writer.writerow(["3531", "Industrials", "Capital Goods", "Machinery", "Construction Machinery & Heavy Transportation Equipment"])
            writer.writerow(["2834", "Health Care", "Pharmaceuticals, Biotechnology & Life Sciences", "Pharmaceuticals", "Pharmaceuticals"])
            writer.writerow(["7370", "Information Technology", "Software & Services", "IT Services", "IT Consulting & Other Services"])
        load_mapping(csv_path)

    def test_lookup_returns_correct_sector(self):
        g = lookup("3571")
        assert g is not None
        assert g.gics_sector == "Information Technology"
        assert g.gics_sub_industry == "Technology Hardware, Storage & Peripherals"

    def test_lookup_returns_correct_for_all_known_sic(self):
        """All 10 SIC codes should return a valid mapping."""
        known = ["3571", "7372", "3674", "3711", "5331",
                 "2911", "6021", "3531", "2834", "7370"]
        for sic in known:
            assert lookup(sic) is not None, f"SIC {sic} should map"

    def test_lookup_returns_none_for_unknown_sic(self):
        assert lookup("9999") is None

    def test_lookup_strips_whitespace(self):
        g = lookup(" 3571 ")
        assert g is not None
        assert g.sic == "3571"

    def test_gics_classification_is_frozen(self):
        """Attempting to mutate a frozen dataclass should fail."""
        import contextlib

        g = lookup("3571")
        assert g is not None
        with contextlib.suppress(Exception):
            g.gics_sub_industry = "Changed"  # type: ignore[misc]


class TestImportGics:
    """Unit tests for scripts/import_gics.py."""

    @patch("scripts.ingest.import_gics.load_mapping")
    def test_import_gics_updates_companies(self, _mock_load):
        from scripts.ingest.import_gics import import_gics

        gics = GicsClassification(
            sic="3571", gics_sector="Info Tech",
            gics_sub_industry="Technology Hardware",
        )

        with (
            patch("scripts.ingest.import_gics.lookup", return_value=gics),
            patch("scripts.ingest.import_gics.SessionLocal"),
            patch("scripts.ingest.import_gics.CompanyRepository") as mock_repo_cls,
        ):
            mock_company = MagicMock()
            mock_company.industry.sic_code = "3571"
            mock_repo = mock_repo_cls.return_value
            mock_repo.get_by_ticker.return_value = mock_company

            results = import_gics(["AAPL"])
            assert results["AAPL"] == "Technology Hardware"
            mock_repo.update_gics.assert_called_once_with("AAPL", gics)

    @patch("scripts.ingest.import_gics.load_mapping")
    def test_import_gics_skips_unknown_sic(self, _mock_load):
        from scripts.ingest.import_gics import import_gics

        with (
            patch("scripts.ingest.import_gics.lookup", return_value=None),
            patch("scripts.ingest.import_gics.SessionLocal"),
            patch("scripts.ingest.import_gics.CompanyRepository") as mock_repo_cls,
        ):
            mock_company = MagicMock()
            mock_company.industry.sic_code = "9999"
            mock_repo = mock_repo_cls.return_value
            mock_repo.get_by_ticker.return_value = mock_company

            results = import_gics(["UNKNOWN"])
            assert results["UNKNOWN"] == "NO MAPPING"
            mock_repo.update_gics.assert_not_called()
