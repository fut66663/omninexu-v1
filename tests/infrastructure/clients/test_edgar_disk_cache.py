"""Tests for EdgarClient raw filing disk cache."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from omninexu.config.data_paths import DataPaths
from omninexu.infrastructure.clients import EdgarClient


class TestEdgarClientDiskCache:
    """Unit tests for the raw filing disk-cache behaviour."""

    @staticmethod
    def _make_mock_filing_with_text() -> MagicMock:
        """Build a mock edgartools filing chain with ``.text()`` support."""
        income_df = pd.DataFrame(
            {
                "concept": [
                    "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax",
                ],
                "label": ["Net sales"],
                "2025-09-27 (FY)": [416161000000.0],
                "dimension": [False],
                "is_breakdown": [False],
            }
        )
        balance_df = pd.DataFrame(
            {
                "concept": ["us-gaap_Assets"],
                "label": ["Total assets"],
                "2025-09-27 (FY)": [364980000000.0],
                "dimension": [False],
                "is_breakdown": [False],
            }
        )
        cashflow_df = pd.DataFrame(
            {
                "concept": ["us-gaap_NetCashProvidedByUsedInOperatingActivities"],
                "label": ["Operating cash flow"],
                "2025-09-27 (FY)": [118254000000.0],
                "dimension": [False],
                "is_breakdown": [False],
            }
        )

        tenk = MagicMock()
        tenk.income_statement.to_dataframe.return_value = income_df
        tenk.balance_sheet.to_dataframe.return_value = balance_df
        tenk.cash_flow_statement.to_dataframe.return_value = cashflow_df

        filing = MagicMock()
        filing.period_of_report = "2025-09-27"
        filing.accession_no = "0000320193-25-000079"
        filing.obj.return_value = tenk
        filing.text.return_value = "SEC FILING CONTENT"

        filings = MagicMock()
        filings.latest.return_value = filing

        company = MagicMock()
        company.cik = "0000320193"
        company.name = "Apple Inc."
        company.sic = "3571"
        company.get_filings.return_value = filings

        return company

    @staticmethod
    def _target_path(root: Path) -> Path:
        """Return the expected disk path for the mock AAPL 10-K under *root*.

        Uses the type-first layout: raw/sec/10-K/{TICKER}/{DATE}/filing.html
        """
        return root / "raw" / "sec" / "10-K" / "AAPL" / "2025-09-27" / "filing.html"

    # ── helpers ────────────────────────────────────────────────────

    @staticmethod
    def _patch_data_paths(tmp_path: Path):
        """Redirect ``data_paths`` used by ``_cache_filing_html`` in edgar_historical."""
        fake_dp = DataPaths(str(tmp_path))
        return patch(
            "omninexu.infrastructure.clients.edgar_historical.data_paths",
            fake_dp,
        )

    def test_first_download_saves_raw_filing_to_disk(self, tmp_path: Path) -> None:
        """After the first download, the raw filing text is on disk."""
        client = EdgarClient()
        mock_company = self._make_mock_filing_with_text()

        with self._patch_data_paths(tmp_path), patch(
            "omninexu.infrastructure.clients.edgar_client.Company",
            return_value=mock_company,
        ):
            client.get_financial_facts("AAPL")

        target = self._target_path(tmp_path)
        assert target.exists(), f"Expected file at {target}"
        assert target.read_text(encoding="utf-8") == "SEC FILING CONTENT"

    def test_second_request_reads_from_disk_not_network(
        self, tmp_path: Path
    ) -> None:
        """When the raw filing exists on disk, ``filing.text()`` is not called."""
        target = self._target_path(tmp_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("PRE_CACHED", encoding="utf-8")

        client = EdgarClient()
        mock_company = self._make_mock_filing_with_text()

        with self._patch_data_paths(tmp_path), patch(
            "omninexu.infrastructure.clients.edgar_client.Company",
            return_value=mock_company,
        ):
            client.get_financial_facts("AAPL")

        # File unchanged — network path was skipped
        assert target.read_text(encoding="utf-8") == "PRE_CACHED"

    def test_disk_cache_preserves_parsed_output(self, tmp_path: Path) -> None:
        """Saving the raw filing must not change the parsed FinancialFacts."""
        client = EdgarClient()
        mock_company = self._make_mock_filing_with_text()

        with self._patch_data_paths(tmp_path), patch(
            "omninexu.infrastructure.clients.edgar_client.Company",
            return_value=mock_company,
        ):
            facts = client.get_financial_facts("AAPL")

        revenue = next(
            (f for f in facts if f.concept == "Revenue" and f.fiscal_year == 2025),
            None,
        )
        assert revenue is not None
        assert revenue.value == pytest.approx(416161000000.0)
        assert revenue.statement_type == "income"

    def test_directory_structure_is_correct(self, tmp_path: Path) -> None:
        """The raw filing is stored under raw/sec/10-K/{TICKER}/{DATE}/filing.html."""
        client = EdgarClient()
        mock_company = self._make_mock_filing_with_text()

        with self._patch_data_paths(tmp_path), patch(
            "omninexu.infrastructure.clients.edgar_client.Company",
            return_value=mock_company,
        ):
            client.get_financial_facts("AAPL")

        target = self._target_path(tmp_path)
        assert target.exists()
        parts = target.parts
        assert "raw" in parts
        assert "sec" in parts
        assert "10-K" in parts
        assert "AAPL" in parts
        assert "2025-09-27" in parts
        assert target.name == "filing.html"

    def test_save_failure_does_not_break_parsing(self, tmp_path: Path) -> None:
        """When ``filing.text()`` raises the method still returns parsed facts."""
        client = EdgarClient()
        mock_company = self._make_mock_filing_with_text()
        mock_company.get_filings().latest().text.side_effect = OSError(
            "Disk full"
        )

        with self._patch_data_paths(tmp_path), patch(
            "omninexu.infrastructure.clients.edgar_client.Company",
            return_value=mock_company,
        ):
            facts = client.get_financial_facts("AAPL")

        assert len(facts) > 0
