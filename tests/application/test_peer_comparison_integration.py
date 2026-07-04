"""Integration tests: peer_comparison with GICS data."""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from omninexu.application.company_context import CompanyContextService
from omninexu.domain.company import Company, IndustryClassification
from omninexu.domain.financials import FinancialFact
from omninexu.infrastructure.db import Base
from omninexu.infrastructure.repositories import (
    CompanyRepository,
    FinancialsRepository,
)
from tests.fakes import FakeCache


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _seed_with_gics(db_session, ticker: str, cik: str, name: str,
                    sub_industry: str, revenue: float, net_income: float) -> None:
    """Seed a company with GICS classification and financial facts."""
    company = Company(
        ticker=ticker, cik=cik, name=name,
        industry=IndustryClassification(
            sic_code="3571",
            gics_sector="Information Technology",
            gics_sub_industry=sub_industry,
        ),
    )
    CompanyRepository(db_session).create_or_update(company)

    facts = [
        FinancialFact(ticker=ticker, fiscal_year=2025, fiscal_period="FY",
                      report_date=date(2025, 9, 30), concept="Revenue",
                      value=revenue),
        FinancialFact(ticker=ticker, fiscal_year=2025, fiscal_period="FY",
                      report_date=date(2025, 9, 30), concept="NetIncome",
                      value=net_income),
    ]
    FinancialsRepository(db_session).save_facts(facts)


class TestPeerComparisonWithGics:
    """End-to-end: GICS filled → peer_comparison returns real rankings."""

    def test_peer_comparison_non_null_with_gics(self, db_session):
        """2+ companies sharing same GICS sub-industry → peer_comparison non-null."""
        _seed_with_gics(db_session, "AAPL", "0000320193", "Apple Inc.",
                        "Technology Hardware", 416e9, 112e9)
        _seed_with_gics(db_session, "MSFT", "0000789019", "Microsoft Corp",
                        "Technology Hardware", 282e9, 102e9)
        _seed_with_gics(db_session, "NVDA", "0001013485", "NVIDIA Corp",
                        "Technology Hardware", 216e9, 120e9)

        cache = FakeCache()
        service = CompanyContextService(db_session, cache_backend=cache)
        ctx = service.build_context("AAPL")

        pc = ctx["peer_comparison"]
        assert pc is not None, "peer_comparison should not be null"
        assert pc["revenue_total_peers"] == 3
        assert 1 <= pc["revenue_rank"] <= 3

    def test_peer_comparison_null_without_gics(self, db_session):
        """Company without gics_sub_industry → peer_comparison remains null."""
        company = Company(
            ticker="AAPL", cik="0000320193", name="Apple Inc.",
            industry=IndustryClassification(sic_code="3571"),
        )
        CompanyRepository(db_session).create_or_update(company)
        FinancialsRepository(db_session).save_facts([
            FinancialFact(ticker="AAPL", fiscal_year=2025, fiscal_period="FY",
                          report_date=date(2025, 9, 30), concept="Revenue",
                          value=416e9),
        ])

        cache = FakeCache()
        service = CompanyContextService(db_session, cache_backend=cache)
        ctx = service.build_context("AAPL")

        assert ctx["peer_comparison"] is None
