"""Unit tests for FinancialFact domain model."""

from datetime import date

import pandas as pd
import pytest

from omninexu.domain.financials import FinancialFact


def _make_fact(fiscal_year: int, concept: str, value: float | None) -> FinancialFact:
    """Create a FinancialFact with minimal required fields."""
    return FinancialFact(
        ticker="AAPL",
        fiscal_year=fiscal_year,
        fiscal_period="FY",
        report_date=date(fiscal_year, 9, 30),
        concept=concept,
        value=value,
    )


class TestFinancialFactToSeries:
    """Tests for FinancialFact.to_series() classmethod."""

    def test_builds_chronological_series(self) -> None:
        """5 facts FY2021-FY2025 → Series indexed [2021..2025] sorted ascending."""
        facts = [_make_fact(y, "Revenue", float(y * 100)) for y in range(2021, 2026)]
        series = FinancialFact.to_series(facts, "Revenue")

        assert series is not None
        assert list(series.index) == [2021, 2022, 2023, 2024, 2025]
        assert len(series) == 5

    def test_sorts_unsorted_input(self) -> None:
        """Shuffled facts → Series sorted by fiscal_year."""
        years = [2023, 2025, 2021, 2024, 2022]
        facts = [_make_fact(y, "Revenue", float(y)) for y in years]
        series = FinancialFact.to_series(facts, "Revenue")

        assert series is not None
        assert list(series.index) == [2021, 2022, 2023, 2024, 2025]

    def test_filters_by_concept(self) -> None:
        """Mixed Revenue + NetIncome → only Revenue values when concept='Revenue'."""
        facts = [
            _make_fact(2025, "Revenue", 100.0),
            _make_fact(2025, "NetIncome", 50.0),
            _make_fact(2024, "Revenue", 90.0),
        ]
        series = FinancialFact.to_series(facts, "Revenue")

        assert series is not None
        assert len(series) == 2
        assert list(series.values) == pytest.approx([90.0, 100.0])

    def test_returns_none_for_empty_list(self) -> None:
        """Empty input → None."""
        assert FinancialFact.to_series([], "Revenue") is None

    def test_returns_none_when_all_values_are_none(self) -> None:
        """All facts have value=None → None."""
        facts = [_make_fact(y, "Revenue", None) for y in range(2021, 2024)]
        assert FinancialFact.to_series(facts, "Revenue") is None

    def test_returns_none_for_no_matching_concept(self) -> None:
        """Revenue facts queried as NetIncome → None."""
        facts = [_make_fact(2025, "Revenue", 100.0)]
        assert FinancialFact.to_series(facts, "NetIncome") is None

    def test_skips_none_values_in_mix(self) -> None:
        """Some facts None, some valid → only valid values in Series."""
        facts = [
            _make_fact(2025, "Revenue", 100.0),
            _make_fact(2024, "Revenue", None),
            _make_fact(2023, "Revenue", 80.0),
        ]
        series = FinancialFact.to_series(facts, "Revenue")

        assert series is not None
        assert len(series) == 2
        assert list(series.values) == pytest.approx([80.0, 100.0])

    def test_single_value_returns_one_element_series(self) -> None:
        """1 fact → Series with 1 element (not None)."""
        facts = [_make_fact(2025, "Revenue", 100.0)]
        series = FinancialFact.to_series(facts, "Revenue")

        assert series is not None
        assert isinstance(series, pd.Series)
        assert len(series) == 1
        assert series.iloc[0] == 100.0

    def test_handles_duplicate_years(self) -> None:
        """Same year + concept twice → both included (dedup happens at DB layer)."""
        facts = [
            _make_fact(2025, "Revenue", 100.0),
            _make_fact(2025, "Revenue", 101.0),  # e.g. restated
        ]
        series = FinancialFact.to_series(facts, "Revenue")

        assert series is not None
        assert len(series) == 2
