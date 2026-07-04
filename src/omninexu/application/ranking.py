"""Ranking and percentile calculations."""

from typing import Any

import pandas as pd


def _safe_float(value: Any) -> float:
    """Convert a value to float, returning 0.0 on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def percentile_rank(series: pd.Series) -> float:
    """Return the percentile rank (0.0 - 1.0) of the last value vs history.

    The result is the percentage of historical values (excluding the last
    value itself) that are strictly below the last value.

    A value of 1.0 means the last value is higher than all previous values.
    A value of 0.0 means the last value is lower than all previous values.
    """
    clean = series.dropna()
    if clean.empty or len(clean) < 2:
        return 0.0

    last_value = clean.iloc[-1]
    history = clean.iloc[:-1]

    below = (history < last_value).sum()
    return _safe_float(below / len(history))


def cagr(series: pd.Series, periods: int) -> float:
    """Calculate compound annual growth rate over the given number of periods.

    The last `periods` values are used. If fewer values are available, the
    longest available history is used.
    """
    clean = series.dropna()
    if clean.empty:
        return 0.0

    available = min(periods, len(clean))
    if available < 2:
        return 0.0

    window = clean.iloc[-available:]
    start_value = window.iloc[0]
    end_value = window.iloc[-1]

    if start_value == 0:
        return 0.0

    years = available - 1
    return _safe_float((end_value / start_value) ** (1 / years) - 1)


def industry_rank(
    values: pd.Series,
    industries: pd.Series,
    target_industry: str,
) -> int:
    """Return the rank of the last value within the target industry.

    Rank 1 means the highest value. Returns 0 if the target industry has no
    valid peers.
    """
    df = pd.DataFrame({"value": values, "industry": industries}).dropna()
    if df.empty:
        return 0

    industry_df = df[df["industry"] == target_industry]
    if industry_df.empty:
        return 0

    # Use rank with method="min" and descending order so largest value is 1.
    ranked = industry_df["value"].rank(method="min", ascending=False)
    return int(ranked.iloc[-1])


class RankingService:
    """Calculate historical percentiles and industry rankings."""

    @staticmethod
    def percentile_rank(series: pd.Series) -> float:
        """Calculate percentile rank of the last value in series."""
        return percentile_rank(series)

    @staticmethod
    def cagr(series: pd.Series, periods: int) -> float:
        """Calculate compound annual growth rate."""
        return cagr(series, periods)

    @staticmethod
    def industry_rank(
        values: pd.Series,
        industries: pd.Series,
        target_industry: str,
    ) -> int:
        """Calculate rank within industry."""
        return industry_rank(values, industries, target_industry)
