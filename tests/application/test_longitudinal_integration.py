"""End-to-end test for longitudinal analysis with multi-year data."""

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


def _seed_aapl_5y(db_session) -> None:
    """Seed AAPL with 5 years of Revenue + NetIncome facts."""
    company = Company(
        ticker="AAPL", cik="0000320193",
        name="Apple Inc.", industry=IndustryClassification(),
    )
    CompanyRepository(db_session).create_or_update(company)

    data = [
        (2021, 365.0, 95.0), (2022, 394.0, 100.0),
        (2023, 383.0, 97.0), (2024, 391.0, 94.0), (2025, 416.0, 112.0),
    ]
    facts = []
    for fy, rev, ni in data:
        facts.append(FinancialFact(
            ticker="AAPL", fiscal_year=fy, fiscal_period="FY",
            report_date=date(fy, 9, 30), concept="Revenue", value=rev * 1e9,
        ))
        facts.append(FinancialFact(
            ticker="AAPL", fiscal_year=fy, fiscal_period="FY",
            report_date=date(fy, 9, 30), concept="NetIncome", value=ni * 1e9,
        ))
    FinancialsRepository(db_session).save_facts(facts)


class TestLongitudinalEndToEnd:
    """Integration: seed multi-year data → build_context → longitudinal has real values."""

    def test_cagr_and_percentile_present_for_both_concepts(self, db_session):
        _seed_aapl_5y(db_session)
        cache = FakeCache()
        service = CompanyContextService(db_session, cache_backend=cache)
        ctx = service.build_context("AAPL")

        lon = ctx["longitudinal"]
        assert lon["revenue_cagr"] > 0
        assert 0 <= lon["revenue_pct_rank"] <= 1
        assert lon["net_income_cagr"] > 0
        assert 0 <= lon["net_income_pct_rank"] <= 1

    def test_confidence_reflects_filled_dimensions(self, db_session):
        _seed_aapl_5y(db_session)
        cache = FakeCache()
        service = CompanyContextService(db_session, cache_backend=cache)
        ctx = service.build_context("AAPL")

        # fundamentals ✅ + longitudinal ✅ → 2/5 dims → "low"
        assert ctx["confidence"] == "low"

    def test_single_year_yields_empty_longitudinal(self, db_session):
        """Regression guard: 1 year data → longitudinal still empty."""
        company = Company(
            ticker="AAPL", cik="0000320193",
            name="Apple Inc.", industry=IndustryClassification(),
        )
        CompanyRepository(db_session).create_or_update(company)
        FinancialsRepository(db_session).save_facts([
            FinancialFact(
                ticker="AAPL", fiscal_year=2025, fiscal_period="FY",
                report_date=date(2025, 9, 30), concept="Revenue", value=416e9,
            )
        ])

        cache = FakeCache()
        service = CompanyContextService(db_session, cache_backend=cache)
        ctx = service.build_context("AAPL")

        assert ctx["longitudinal"] == {}
