"""Insider transaction domain model (Form 4 filings)."""

from dataclasses import dataclass
from datetime import date


@dataclass
class InsiderTrade:
    """A single insider transaction reported in a Form 4 filing."""

    ticker: str
    insider_name: str
    insider_title: str | None = None
    transaction_type: str = ""       # 'P' (purchase) or 'S' (sale)
    shares: float | None = None
    price: float | None = None
    transaction_date: date | None = None
    source_filing: str | None = None
