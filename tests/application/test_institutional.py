"""Tests for institutional holdings application service."""

from datetime import date
from unittest.mock import MagicMock

from omninexu.api.schemas.company import InstitutionalSummary
from omninexu.application.institutional import build_institutional_summary
from omninexu.domain.institutional import InstitutionalHolding


def _make_holdings(count: int = 10) -> list[InstitutionalHolding]:
    """Build a list of InstitutionalHolding domain objects."""
    return [
        InstitutionalHolding(
            ticker="AAPL", reporting_manager=f"Institution {i}",
            shares=1000.0 * (10 - i), value=50000.0 * (10 - i),
            report_date=date(2025, 3, 31),
            source_filing=f"0000{i:04d}-25-000001",
        )
        for i in range(count)
    ]


class TestBuildInstitutionalSummary:
    """Unit tests for build_institutional_summary()."""

    def test_returns_none_when_no_holdings(self):
        repo = MagicMock()
        repo.get_holdings.return_value = []
        assert build_institutional_summary("AAPL", repo) is None

    def test_returns_top_10_sorted_by_value(self):
        repo = MagicMock()
        repo.get_holdings.return_value = _make_holdings(12)

        result = build_institutional_summary("AAPL", repo)
        assert isinstance(result, InstitutionalSummary)
        assert len(result.top_holders) == 10
        # First should be highest value
        assert result.top_holders[0].value > result.top_holders[1].value

    def test_source_filing_url_generated(self):
        repo = MagicMock()
        repo.get_holdings.return_value = _make_holdings(1)

        result = build_institutional_summary("AAPL", repo)
        assert result is not None
        url = result.top_holders[0].source_filing_url
        assert "sec.gov" in url
        assert "13F-HR" in url

    def test_as_of_date_from_first_holding(self):
        repo = MagicMock()
        repo.get_holdings.return_value = _make_holdings(3)

        result = build_institutional_summary("AAPL", repo)
        assert result is not None
        assert result.as_of_date == date(2025, 3, 31)

    def test_fewer_than_10_returns_all(self):
        repo = MagicMock()
        repo.get_holdings.return_value = _make_holdings(3)

        result = build_institutional_summary("AAPL", repo)
        assert result is not None
        assert len(result.top_holders) == 3
