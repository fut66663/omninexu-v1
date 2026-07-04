"""End-to-end integration tests for insider trading in CompanyContext."""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from omninexu.application.company_context import CompanyContextService
from omninexu.domain.company import Company, IndustryClassification
from omninexu.domain.financials import FinancialFact
from omninexu.domain.insider import InsiderTrade
from omninexu.infrastructure.db import Base
from omninexu.infrastructure.repositories import (
    CompanyRepository,
    FinancialsRepository,
    InsiderRepository,
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


def _seed(db_session):
    CompanyRepository(db_session).create_or_update(Company(
        ticker="AAPL", cik="0000320193", name="Apple Inc.",
        industry=IndustryClassification(sic_code="3571"),
    ))
    FinancialsRepository(db_session).save_facts([
        FinancialFact(ticker="AAPL", fiscal_year=2025, fiscal_period="FY",
                      report_date=date(2025, 9, 30), concept="Revenue",
                      value=416e9),
    ])


class TestInsiderIntegration:
    """End-to-end: DB → CompanyContextService → insider in response."""

    def test_insider_non_null_with_trades(self, db_session):
        _seed(db_session)
        InsiderRepository(db_session).save_trades("AAPL", [
            InsiderTrade(ticker="AAPL", insider_name="Tim Cook",
                         insider_title="CEO", transaction_type="S",
                         shares=100000.0, price=195.0,
                         transaction_date=date.today(),
                         source_filing="ACC-001"),
        ])

        cache = FakeCache()
        service = CompanyContextService(db_session, cache_backend=cache)
        ctx = service.build_context("AAPL")

        ins = ctx["insider"]
        assert ins is not None, "insider should not be null"
        assert ins["transaction_count_90d"] == 1
        assert ins["net_shares_90d"] == -100000.0

    def test_insider_null_without_trades(self, db_session):
        _seed(db_session)

        cache = FakeCache()
        service = CompanyContextService(db_session, cache_backend=cache)
        ctx = service.build_context("AAPL")

        assert ctx["insider"] is None

    def test_net_shares_aggregates_correctly(self, db_session):
        _seed(db_session)
        InsiderRepository(db_session).save_trades("AAPL", [
            InsiderTrade(ticker="AAPL", insider_name="Buyer", transaction_type="P",
                         shares=5000.0, transaction_date=date.today()),
            InsiderTrade(ticker="AAPL", insider_name="Seller", transaction_type="S",
                         shares=2000.0, transaction_date=date.today()),
        ])

        cache = FakeCache()
        service = CompanyContextService(db_session, cache_backend=cache)
        ctx = service.build_context("AAPL")

        ins = ctx["insider"]
        assert ins is not None
        assert ins["net_shares_90d"] == 3000.0  # +5000 - 2000
        assert ins["transaction_count_90d"] == 2
