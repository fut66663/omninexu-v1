"""Company domain model."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class IndustryClassification:
    """Industry classification codes."""

    sic_code: str | None = None
    naics_code: str | None = None
    gics_sector: str | None = None
    gics_industry_group: str | None = None
    gics_industry: str | None = None
    gics_sub_industry: str | None = None


@dataclass
class Company:
    """Company domain entity."""

    ticker: str
    cik: str
    name: str
    industry: IndustryClassification
    is_snp500: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        self.ticker = self.ticker.upper()
