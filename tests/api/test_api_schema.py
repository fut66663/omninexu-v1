"""Tests for API response Pydantic schemas."""

from datetime import date

from omninexu.api.schemas.company import (
    CompanyContextResponse,
    FundamentalMetric,
    InsiderSummary,
    InsiderTransaction,
    InstitutionalHolder,
    InstitutionalSummary,
    Source,
)


def test_institutional_holder_fields():
    h = InstitutionalHolder(
        name="Vanguard Group", shares=1320000000,
        value=328000000000.0, source_filing_url="https://sec.gov/...",
    )
    data = h.model_dump()
    assert data["name"] == "Vanguard Group"
    assert data["shares"] == 1320000000
    assert data["value"] == 328000000000.0


def test_institutional_summary_with_top_holders():
    holders = [
        InstitutionalHolder(name="Vanguard", shares=1000, value=50000.0, source_filing_url=""),
        InstitutionalHolder(name="BlackRock", shares=800, value=40000.0, source_filing_url=""),
    ]
    summary = InstitutionalSummary(top_holders=holders, as_of_date=date(2025, 6, 30))
    data = summary.model_dump()
    assert len(data["top_holders"]) == 2
    assert data["as_of_date"] == date(2025, 6, 30)


def test_insider_transaction_fields():
    tx = InsiderTransaction(
        insider_name="Tim Cook", insider_title="CEO",
        transaction_type="S", shares=100000.0,
        price=195.50, transaction_date=date(2025, 6, 15),
    )
    data = tx.model_dump()
    assert data["insider_name"] == "Tim Cook"
    assert data["transaction_type"] == "S"
    assert data["transaction_date"] == date(2025, 6, 15)


def test_insider_summary_aggregation():
    txs = [
        InsiderTransaction(insider_name="A", transaction_type="S",
                          shares=5000.0, transaction_date=date(2025, 6, 1)),
    ]
    summary = InsiderSummary(
        recent_transactions=txs, net_shares_90d=-5000.0, transaction_count_90d=1,
    )
    assert summary.model_dump()["net_shares_90d"] == -5000.0
    assert summary.model_dump()["transaction_count_90d"] == 1


def test_company_context_response_accepts_new_fields():
    """Response can be constructed with institutional and insider set."""
    resp = CompanyContextResponse(
        ticker="AAPL", cik="0000320193", name="Apple Inc.",
        as_of_date=None, fundamentals={}, longitudinal={},
        peer_comparison=None,
        institutional=InstitutionalSummary(top_holders=[], as_of_date=None),
        insider=InsiderSummary(recent_transactions=[], net_shares_90d=0.0,
                               transaction_count_90d=0),
        sources=[], confidence="high",
    )
    assert resp.institutional is not None
    assert resp.insider is not None


def test_company_context_response_accepts_none():
    """Old clients that omit institutional/insider should still work."""
    resp = CompanyContextResponse(
        ticker="AAPL", cik="0000320193", name="Apple Inc.",
        as_of_date=None,
        fundamentals={"revenue": FundamentalMetric(value=100.0, unit="USD", fiscal_year=2025)},
        longitudinal={}, peer_comparison=None,
        sources=[Source(type="10-K", url="https://sec.gov/...")],
        confidence="low",
    )
    assert resp.institutional is None
    assert resp.insider is None
    assert resp.fundamentals["revenue"].value == 100.0
