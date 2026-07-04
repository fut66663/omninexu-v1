"""Institutional holding domain model (13F filings)."""

from dataclasses import dataclass
from datetime import date


@dataclass
class InstitutionalHolding:
    """A single institutional position reported in a 13F filing."""

    ticker: str
    reporting_manager: str
    cusip: str | None = None
    shares: float | None = None
    value: float | None = None
    report_date: date | None = None
    source_filing: str | None = None
