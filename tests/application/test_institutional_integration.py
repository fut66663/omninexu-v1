"""End-to-end integration tests for institutional holdings in CompanyContext."""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from omninexu.application.company_context import CompanyContextService
from omninexu.domain.company import Company, IndustryClassification
from omninexu.domain.financials import FinancialFact
from omninexu.domain.institutional import InstitutionalHolding
from omninexu.infrastructure.db import Base
from omninexu.infrastructure.repositories import (
    CompanyRepository,
    FinancialsRepository,
    InstitutionalRepository,
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


def _seed_company(db_session, ticker="AAPL", cik="0000320193", name="Apple Inc."):
    company = Company(
        ticker=ticker, cik=cik, name=name,
        industry=IndustryClassification(sic_code="3571"),
    )
    CompanyRepository(db_session).create_or_update(company)
    FinancialsRepository(db_session).save_facts([
        FinancialFact(ticker=ticker, fiscal_year=2025, fiscal_period="FY",
                      report_date=date(2025, 9, 30), concept="Revenue",
                      value=416e9),
    ])


class TestInstitutionalIntegration:
    """End-to-end: DB → CompanyContextService → institutional in response."""

    def test_institutional_non_null_with_holdings(self, db_session):
        _seed_company(db_session)
        InstitutionalRepository(db_session).save_holdings("AAPL", [
            InstitutionalHolding(ticker="AAPL", reporting_manager="Vanguard",
                                 shares=1.3e9, value=3.2e11,
                                 report_date=date(2025, 3, 31),
                                 source_filing="0000102909-25-000001"),
            InstitutionalHolding(ticker="AAPL", reporting_manager="BlackRock",
                                 shares=1.0e9, value=2.6e11,
                                 report_date=date(2025, 3, 31),
                                 source_filing="0001364742-25-000001"),
        ])

        cache = FakeCache()
        service = CompanyContextService(db_session, cache_backend=cache)
        ctx = service.build_context("AAPL")

        inst = ctx["institutional"]
        assert inst is not None, "institutional should not be null"
        assert len(inst["top_holders"]) == 2
        assert inst["top_holders"][0]["name"] == "Vanguard"
        assert "sec.gov" in inst["top_holders"][0]["source_filing_url"]

    def test_institutional_null_without_holdings(self, db_session):
        _seed_company(db_session)

        cache = FakeCache()
        service = CompanyContextService(db_session, cache_backend=cache)
        ctx = service.build_context("AAPL")

        assert ctx["institutional"] is None

    def test_confidence_reflects_institutional_filled(self, db_session):
        _seed_company(db_session)
        InstitutionalRepository(db_session).save_holdings("AAPL", [
            InstitutionalHolding(ticker="AAPL", reporting_manager="Vanguard",
                                 shares=1e9, value=1e11,
                                 report_date=date(2025, 3, 31)),
        ])

        cache = FakeCache()
        service = CompanyContextService(db_session, cache_backend=cache)
        ctx = service.build_context("AAPL")

        # fundamentals ✅ + longitudinal ❌(only 1yr) + institutional ✅ = 2 → "low"
        assert ctx["confidence"] in ("low", "medium")
