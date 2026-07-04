"""Financial domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


@dataclass
class FinancialFact:
    """A single financial fact extracted from SEC filings."""

    ticker: str
    fiscal_year: int
    fiscal_period: str  # 'FY', 'Q1', 'Q2', 'Q3'
    report_date: date
    concept: str
    value: float | None
    unit: str = "USD"
    source_filing: str | None = None
    statement_type: str | None = None
    source: str = "simfin"  # "simfin" | "edgar"

    @classmethod
    def to_series(
        cls,
        facts: list[FinancialFact],
        concept: str,
    ) -> pd.Series | None:
        """Build a chronologically-sorted Series for a single concept.

        Returns ``None`` when no facts match the given concept or all
        matched facts have ``value=None``.
        """
        import pandas as pd

        records = sorted(
            ((f.fiscal_year, f.value) for f in facts
             if f.concept == concept and f.value is not None),
            key=lambda x: x[0],
        )
        if not records:
            return None
        years, values = zip(*records, strict=True)
        return pd.Series(values, index=years)


@dataclass
class FinancialMetric:
    """A computed financial metric."""

    ticker: str
    metric_name: str
    value: float
    fiscal_year: int
    percentile: float | None = None
    industry_rank: int | None = None
    industry_percentile: float | None = None
