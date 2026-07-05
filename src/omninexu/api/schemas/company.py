"""Pydantic schemas for company API responses."""

from datetime import date

from pydantic import BaseModel, ConfigDict


class FundamentalMetric(BaseModel):
    """A single standardized financial metric."""

    model_config = ConfigDict(extra="forbid")
    value: float
    unit: str
    fiscal_year: int
    source: str  # "simfin" | "edgar"


class PeerComparison(BaseModel):
    """Peer ranking within the same GICS sub-industry.

    Fields are optional because some concepts (e.g. Revenue for
    financial-sector companies) may not be comparable across peers.
    """

    model_config = ConfigDict(extra="forbid")
    revenue_rank: int | None = None
    revenue_total_peers: int | None = None
    net_income_rank: int | None = None
    net_income_total_peers: int | None = None


class Source(BaseModel):
    """A source filing reference."""

    model_config = ConfigDict(extra="forbid")
    type: str  # "10-K", "13F-HR", "Form-4"
    url: str


class InstitutionalHolder(BaseModel):
    """A single institutional holder from 13F data."""

    model_config = ConfigDict(extra="forbid")
    name: str
    shares: int
    value: float
    source_filing_url: str


class InstitutionalSummary(BaseModel):
    """Aggregated institutional holdings from 13F filings."""

    model_config = ConfigDict(extra="forbid")
    top_holders: list[InstitutionalHolder]
    as_of_date: date | None = None
    source: str = "SEC 13F"


class InsiderTransaction(BaseModel):
    """A single insider transaction from Form 4."""

    model_config = ConfigDict(extra="forbid")
    insider_name: str
    insider_title: str | None = None
    transaction_type: str  # 'P' (purchase) or 'S' (sale)
    shares: float
    price: float | None = None
    transaction_date: date


class InsiderSummary(BaseModel):
    """Aggregated insider trading summary (last 90 days)."""

    model_config = ConfigDict(extra="forbid")
    recent_transactions: list[InsiderTransaction]
    net_shares_90d: float
    transaction_count_90d: int
    source: str = "SEC Form-4"


class CompanyContextResponse(BaseModel):
    """Full company context response returned by /v1/company/context."""

    model_config = ConfigDict(extra="forbid")

    ticker: str
    cik: str
    name: str
    as_of_date: date | None
    fundamentals: dict[str, FundamentalMetric]
    longitudinal: dict[str, float]
    peer_comparison: PeerComparison | None
    institutional: InstitutionalSummary | None = None
    insider: InsiderSummary | None = None
    sources: list[Source]
    confidence: str
