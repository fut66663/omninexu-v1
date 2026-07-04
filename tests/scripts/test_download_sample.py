"""Tests for scripts/ingest/download_sample.py."""

import json
from datetime import date
from unittest.mock import patch

from omninexu.domain.financials import FinancialFact
from scripts.ingest.download_sample import download_sample, fact_to_dict, save_fixture


class TestFactToDict:
    def test_serializes_financial_fact(self):
        fact = FinancialFact(
            ticker="AAPL",
            fiscal_year=2025,
            fiscal_period="FY",
            report_date=date(2025, 9, 27),
            concept="Revenue",
            value=416_161_000_000.0,
            unit="USD",
            source_filing="10-K",
        )
        result = fact_to_dict(fact)
        assert result["ticker"] == "AAPL"
        assert result["fiscal_year"] == 2025
        assert result["concept"] == "Revenue"
        assert result["value"] == 416_161_000_000.0
        assert result["report_date"] == "2025-09-27"

    def test_serializes_fact_with_none_statements(self):
        fact = FinancialFact(
            ticker="MSFT",
            fiscal_year=2024,
            fiscal_period="FY",
            report_date=date(2024, 6, 30),
            concept="NetIncome",
            value=88_136_000_000.0,
            unit="USD",
        )
        result = fact_to_dict(fact)
        assert result["ticker"] == "MSFT"


class TestDownloadSample:
    def test_download_sample_returns_facts(self):
        facts = [
            FinancialFact(
                ticker="AAPL",
                fiscal_year=2025,
                fiscal_period="FY",
                report_date=date(2025, 9, 27),
                concept="Revenue",
                value=416_161_000_000.0,
                unit="USD",
            ),
        ]

        with patch("scripts.ingest.download_sample.EdgarClient") as mock_client_cls:
            mock_client = mock_client_cls.return_value
            mock_client.get_financial_facts.return_value = facts

            result = download_sample(["AAPL"])
            assert "AAPL" in result
            assert len(result["AAPL"]) == 1
            assert result["AAPL"][0]["concept"] == "Revenue"

    def test_download_sample_default_tickers(self):
        with patch("scripts.ingest.download_sample.EdgarClient") as mock_client_cls:
            mock_client = mock_client_cls.return_value
            mock_client.get_financial_facts.return_value = []

            result = download_sample()
            assert len(result) == 3  # AAPL, MSFT, NVDA


class TestSaveFixture:
    def test_save_fixture_writes_json(self, tmp_path):
        data = {"AAPL": [{"concept": "Revenue", "value": 100.0}]}
        path = tmp_path / "fixtures" / "sample.json"
        result = save_fixture(data, path)
        assert result == path
        assert path.exists()
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["AAPL"][0]["concept"] == "Revenue"

    def test_save_fixture_creates_parent_dir(self, tmp_path):
        data = {"MSFT": []}
        path = tmp_path / "deep" / "nested" / "output.json"
        result = save_fixture(data, path)
        assert result.exists()
