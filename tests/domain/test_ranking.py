"""Tests for ranking calculations."""

import pandas as pd
import pytest

from omninexu.application.ranking import (
    RankingService,
    _safe_float,
    cagr,
    industry_rank,
    percentile_rank,
)


class TestPercentileRank:
    """Tests for percentile_rank."""

    def test_percentile_rank_last_value_is_highest(self):
        """If last value is highest, percentile rank should be 1.0."""
        series = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        assert percentile_rank(series) == pytest.approx(1.0)

    def test_percentile_rank_last_value_is_lowest(self):
        """If last value is lowest, percentile rank should be 0.0."""
        series = pd.Series([5.0, 4.0, 3.0, 2.0, 1.0])
        assert percentile_rank(series) == pytest.approx(0.0)

    def test_percentile_rank_empty_series(self):
        """Empty series should return 0.0."""
        series = pd.Series([], dtype=float)
        assert percentile_rank(series) == pytest.approx(0.0)

    def test_percentile_rank_single_value(self):
        """Single value series should return 0.0."""
        series = pd.Series([5.0])
        assert percentile_rank(series) == pytest.approx(0.0)

    def test_percentile_rank_with_nan(self):
        """NaN values should be ignored."""
        series = pd.Series([1.0, 2.0, float("nan"), 4.0, 3.0])
        # history [1.0, 2.0, 4.0], last 3.0 -> 2 out of 3 below
        assert percentile_rank(series) == pytest.approx(2.0 / 3.0)


class TestCagr:
    """Tests for cagr."""

    def test_cagr_basic(self):
        """CAGR over 5 periods with doubling value."""
        series = pd.Series([100.0, 100.0, 100.0, 100.0, 200.0])
        # 4 years from 100 to 200 -> ~18.9%
        result = cagr(series, periods=5)
        assert result == pytest.approx(0.1892, abs=0.001)

    def test_cagr_with_insufficient_data(self):
        """If fewer than 2 values, CAGR should be 0.0."""
        series = pd.Series([100.0])
        assert cagr(series, periods=5) == pytest.approx(0.0)

    def test_cagr_with_zero_start(self):
        """If start value is 0, CAGR should be 0.0."""
        series = pd.Series([0.0, 100.0, 200.0])
        assert cagr(series, periods=3) == pytest.approx(0.0)

    def test_cagr_empty_series(self):
        """Empty series should return 0.0."""
        series = pd.Series([], dtype=float)
        assert cagr(series, periods=5) == pytest.approx(0.0)

    def test_cagr_uses_longest_available(self):
        """If series shorter than requested periods, use longest available."""
        series = pd.Series([100.0, 200.0])
        # 1 year from 100 to 200 -> 100%
        assert cagr(series, periods=5) == pytest.approx(1.0)


class TestIndustryRank:
    """Tests for industry_rank."""

    def test_industry_rank_basic(self):
        """Last value should be ranked within its industry."""
        values = pd.Series([100.0, 200.0, 300.0, 150.0])
        industries = pd.Series(["tech", "tech", "tech", "health"])
        assert industry_rank(values, industries, "tech") == 1

    def test_industry_rank_not_top(self):
        """Last value is not the highest in industry."""
        values = pd.Series([300.0, 100.0, 200.0, 150.0])
        industries = pd.Series(["tech", "tech", "tech", "health"])
        # Last tech value is 200, rank should be 2 (after 300)
        assert industry_rank(values, industries, "tech") == 2

    def test_industry_rank_empty_industry(self):
        """Target industry not present should return 0."""
        values = pd.Series([100.0, 200.0])
        industries = pd.Series(["tech", "tech"])
        assert industry_rank(values, industries, "health") == 0

    def test_industry_rank_empty_data(self):
        """Empty data should return 0."""
        values = pd.Series([], dtype=float)
        industries = pd.Series([], dtype=str)
        assert industry_rank(values, industries, "tech") == 0


class TestRankingService:
    """Tests for RankingService class wrapper."""

    def test_ranking_service_percentile_rank(self):
        series = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        assert RankingService.percentile_rank(series) == pytest.approx(1.0)

    def test_ranking_service_cagr(self):
        series = pd.Series([100.0, 100.0, 100.0, 100.0, 200.0])
        result = RankingService.cagr(series, periods=5)
        assert result == pytest.approx(0.1892, abs=0.001)

    def test_ranking_service_industry_rank(self):
        values = pd.Series([100.0, 200.0, 300.0])
        industries = pd.Series(["tech", "tech", "tech"])
        assert RankingService.industry_rank(values, industries, "tech") == 1


def test_safe_float_converts_valid_values():
    """_safe_float should convert strings and numbers to float."""
    assert _safe_float("3.14") == pytest.approx(3.14)
    assert _safe_float(42) == pytest.approx(42.0)


def test_safe_float_returns_zero_on_invalid_input():
    """_safe_float should return 0.0 for non-numeric inputs."""
    assert _safe_float(None) == 0.0
    assert _safe_float("not-a-number") == 0.0
    assert _safe_float(object()) == 0.0
