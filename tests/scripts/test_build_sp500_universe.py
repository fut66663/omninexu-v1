"""Tests for scripts/ingest/build_sp500_universe.py."""

import json
from unittest.mock import patch

from scripts.ingest.build_sp500_universe import (
    _assign_day,
    _format_cik,
    _load_companies,
    main,
)


class TestFormatCik:
    def test_pads_short_cik(self):
        assert _format_cik("320193") == "0000320193"

    def test_handles_already_padded_cik(self):
        assert _format_cik("0000320193") == "0000320193"

    def test_handles_cik_with_whitespace(self):
        assert _format_cik(" 320193 ") == "0000320193"


class TestAssignDay:
    def test_it_sector_goes_to_day1(self):
        company = {"ticker": "AAPL", "gics_sector": "Information Technology"}
        assert _assign_day(company) == 1

    def test_communication_services_goes_to_day1(self):
        company = {"ticker": "GOOGL", "gics_sector": "Communication Services"}
        assert _assign_day(company) == 1

    def test_energy_goes_to_day2(self):
        company = {"ticker": "XOM", "gics_sector": "Energy"}
        assert _assign_day(company) == 2

    def test_industrials_goes_to_day2(self):
        company = {"ticker": "CAT", "gics_sector": "Industrials"}
        assert _assign_day(company) == 2

    def test_financials_goes_to_day3(self):
        company = {"ticker": "JPM", "gics_sector": "Financials"}
        assert _assign_day(company) == 3

    def test_real_estate_goes_to_day3(self):
        company = {"ticker": "O", "gics_sector": "Real Estate"}
        assert _assign_day(company) == 3

    def test_health_care_goes_to_day4(self):
        company = {"ticker": "PFE", "gics_sector": "Health Care"}
        assert _assign_day(company) == 4

    def test_consumer_staples_goes_to_day4(self):
        company = {"ticker": "WMT", "gics_sector": "Consumer Staples"}
        assert _assign_day(company) == 4

    def test_consumer_discretionary_goes_to_day5(self):
        company = {"ticker": "TSLA", "gics_sector": "Consumer Discretionary"}
        assert _assign_day(company) == 5

    def test_utilities_goes_to_day5(self):
        company = {"ticker": "AEP", "gics_sector": "Utilities"}
        assert _assign_day(company) == 5

    def test_materials_goes_to_day5(self):
        company = {"ticker": "NEM", "gics_sector": "Materials"}
        assert _assign_day(company) == 5

    def test_data_center_reit_goes_to_day1(self):
        """Data center REITs go to Day 1 regardless of sector."""
        company = {"ticker": "EQIX", "gics_sector": "Real Estate"}
        assert _assign_day(company) == 1

    def test_unknown_sector_falls_back_to_day5(self):
        company = {"ticker": "ZZZZ", "gics_sector": "Unknown"}
        assert _assign_day(company) == 5


class TestLoadCompanies:
    def test_loads_csv_with_headers(self, tmp_path):
        csv_path = tmp_path / "test_constituents.csv"
        csv_path.write_text(
            "Symbol,Security,CIK,GICS Sector,GICS Sub-Industry\r\n"
            "AAPL,Apple Inc.,0000320193,Information Technology,Technology Hardware\r\n"
            "MSFT,Microsoft Corp,0000789019,Information Technology,Software\r\n",
            encoding="utf-8",
        )

        with patch("scripts.ingest.build_sp500_universe.CSV_PATH", csv_path):
            companies = _load_companies()
            assert len(companies) == 2
            assert companies[0]["ticker"] == "AAPL"
            assert companies[0]["cik"] == "0000320193"
            assert companies[1]["ticker"] == "MSFT"


class TestMain:
    def test_main_generates_json_outputs(self, tmp_path):
        """main() should produce per-day and combined JSON files."""
        csv_path = tmp_path / "sp500_constituents.csv"
        csv_path.write_text(
            "Symbol,Security,CIK,GICS Sector,GICS Sub-Industry\r\n"
            "AAPL,Apple Inc.,0000320193,Information Technology,Hardware\r\n"
            "XOM,Exxon Mobil,0000034088,Energy,Integrated Oil & Gas\r\n"
            "JPM,JPMorgan Chase,0000019617,Financials,Banks\r\n",
            encoding="utf-8",
        )

        out_dir = tmp_path / "out"
        out_dir.mkdir()

        with (
            patch("scripts.ingest.build_sp500_universe.CSV_PATH", csv_path),
            patch("scripts.ingest.build_sp500_universe.OUT_DIR", out_dir),
        ):
            main()

            # Check per-day files exist
            for day in range(1, 6):
                assert (out_dir / f"sp500_universe_day{day}.json").exists()

            # Check all.json
            all_path = out_dir / "sp500_universe_all.json"
            assert all_path.exists()
            all_data = json.loads(all_path.read_text(encoding="utf-8"))
            assert len(all_data) == 3
