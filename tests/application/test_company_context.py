"""Tests for CompanyContextService."""

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
from tests.fakes import FailingDataSource, FakeCache, FakeDataSource


@pytest.fixture
def db_session():
    """Create an in-memory SQLite session for service tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def fake_cache():
    """Provide a fresh in-memory FakeCache for each test."""
    return FakeCache()


def _make_service(db_session, fake_cache, data_source=None):
    """Create a CompanyContextService using FakeCache for hermetic tests."""
    return CompanyContextService(
        db_session,
        data_source=data_source,
        cache_backend=fake_cache,
    )




def _seed_company_and_facts(db_session):
    """Helper to seed AAPL company and a Revenue fact."""
    company_repo = CompanyRepository(db_session)
    fin_repo = FinancialsRepository(db_session)

    company = Company(
        ticker="AAPL",
        cik="0000320193",
        name="Apple Inc.",
        industry=IndustryClassification(sic_code="3571"),
    )
    company_repo.create_or_update(company)

    facts = [
        FinancialFact(
            ticker="AAPL",
            fiscal_year=2025,
            fiscal_period="FY",
            report_date=date(2025, 9, 27),
            concept="Revenue",
            value=416_161_000_000.0,
        )
    ]
    fin_repo.save_facts(facts)
    return facts


class TestFundamentals:
    """Tests for Part 2: Company Context fundamentals."""

    def test_build_context_returns_fundamentals(self, db_session, fake_cache):
        """Context should include fundamentals section."""
        _seed_company_and_facts(db_session)
        service = _make_service(db_session, fake_cache)

        context = service.build_context("AAPL")

        assert "fundamentals" in context
        assert context["ticker"] == "AAPL"
        assert context["cik"] == "0000320193"

    def test_build_context_for_aapl_contains_revenue(self, db_session, fake_cache):
        """AAPL context should contain Revenue in fundamentals."""
        _seed_company_and_facts(db_session)
        service = _make_service(db_session, fake_cache)

        context = service.build_context("AAPL")

        revenue = context["fundamentals"]["revenue"]
        assert revenue["value"] == 416_161_000_000.0
        assert revenue["unit"] == "USD"
        assert revenue["fiscal_year"] == 2025

    def test_build_context_creates_missing_company(self, db_session, fake_cache):
        """If company is not in DB, service should fetch from Edgar and create it."""
        CompanyRepository(db_session).create_or_update(
            Company(
                ticker="AAPL",
                cik="0000320193",
                name="Apple Inc.",
                industry=IndustryClassification(),
            )
        )
        fin_repo = FinancialsRepository(db_session)
        fin_repo.save_facts(
            [
                FinancialFact(
                    ticker="AAPL",
                    fiscal_year=2025,
                    fiscal_period="FY",
                    report_date=date(2025, 9, 27),
                    concept="Revenue",
                    value=100.0,
                )
            ]
        )

        service = _make_service(
            db_session,
            fake_cache,
            data_source=FakeDataSource(),
        )
        context = service.build_context("AAPL")

        assert context["name"] == "Apple Inc."
        assert context["fundamentals"]["revenue"]["value"] == 100.0

    def test_build_context_invalid_ticker_raises(self, db_session, fake_cache):
        """Invalid ticker should raise TickerNotFoundError from data source."""
        from omninexu.observability import TickerNotFoundError

        service = _make_service(
            db_session,
            fake_cache,
            data_source=FailingDataSource(),
        )

        with pytest.raises(TickerNotFoundError):
            service.build_context("INVALID")

    def test_build_context_no_financial_data_raises(self, db_session, fake_cache):
        """Company without financial data should raise FinancialDataNotFoundError."""
        from omninexu.observability import FinancialDataNotFoundError

        company = Company(
            ticker="AAPL",
            cik="0000320193",
            name="Apple Inc.",
            industry=IndustryClassification(),
        )
        CompanyRepository(db_session).create_or_update(company)

        service = _make_service(db_session, fake_cache)

        with pytest.raises(FinancialDataNotFoundError):
            service.build_context("AAPL")


class TestLongitudinal:
    """Tests for Part 3: longitudinal analysis."""

    def _seed_multi_year_facts(self, db_session):
        """Seed AAPL Revenue facts for multiple years."""
        company = Company(
            ticker="AAPL",
            cik="0000320193",
            name="Apple Inc.",
            industry=IndustryClassification(),
        )
        CompanyRepository(db_session).create_or_update(company)

        facts = [
            FinancialFact(
                ticker="AAPL",
                fiscal_year=year,
                fiscal_period="FY",
                report_date=date(year, 9, 30),
                concept="Revenue",
                value=float(value),
            )
            for year, value in [(2021, 100), (2022, 110), (2023, 121), (2024, 133), (2025, 146)]
        ]
        FinancialsRepository(db_session).save_facts(facts)

    def test_build_context_longitudinal_contains_cagr(self, db_session, fake_cache):
        """Context should include Revenue CAGR."""
        self._seed_multi_year_facts(db_session)
        service = _make_service(db_session, fake_cache)

        context = service.build_context("AAPL")

        assert "revenue_cagr" in context["longitudinal"]
        assert context["longitudinal"]["revenue_cagr"] > 0

    def test_build_context_longitudinal_contains_percentile(self, db_session, fake_cache):
        """Context should include Revenue percentile rank."""
        self._seed_multi_year_facts(db_session)
        service = _make_service(db_session, fake_cache)

        context = service.build_context("AAPL")

        assert "revenue_pct_rank" in context["longitudinal"]
        # Last value 146 is highest in ascending series -> 100% percentile
        assert context["longitudinal"]["revenue_pct_rank"] == pytest.approx(1.0)

    def test_build_context_longitudinal_handles_insufficient_history(self, db_session, fake_cache):
        """If only one year of data, longitudinal should be empty for that concept."""
        _seed_company_and_facts(db_session)
        service = _make_service(db_session, fake_cache)

        context = service.build_context("AAPL")

        assert "revenue_cagr" not in context["longitudinal"]
        assert "revenue_pct_rank" not in context["longitudinal"]


class TestPeerComparison:
    """Tests for Part 4: peer comparison analysis."""

    def _seed_peers(self, db_session):
        """Seed AAPL, MSFT, NVDA in the same GICS sub-industry."""
        company_repo = CompanyRepository(db_session)
        fin_repo = FinancialsRepository(db_session)

        peers = [
            ("AAPL", "0000320193", "Apple Inc.", 300.0, 80.0),
            ("MSFT", "0000789019", "Microsoft Corp", 250.0, 70.0),
            ("NVDA", "0001013485", "NVIDIA Corp", 400.0, 90.0),
        ]
        sub_industry = "Semiconductors"

        for ticker, cik, name, revenue, net_income in peers:
            company = Company(
                ticker=ticker,
                cik=cik,
                name=name,
                industry=IndustryClassification(gics_sub_industry=sub_industry),
            )
            company_repo.create_or_update(company)

            facts = [
                FinancialFact(
                    ticker=ticker,
                    fiscal_year=2025,
                    fiscal_period="FY",
                    report_date=date(2025, 9, 27),
                    concept="Revenue",
                    value=revenue,
                ),
                FinancialFact(
                    ticker=ticker,
                    fiscal_year=2025,
                    fiscal_period="FY",
                    report_date=date(2025, 9, 27),
                    concept="NetIncome",
                    value=net_income,
                ),
            ]
            fin_repo.save_facts(facts)

    def test_build_context_peer_comparison_with_peers(self, db_session, fake_cache):
        """Peer comparison should include ranks and peer counts."""
        self._seed_peers(db_session)
        service = _make_service(db_session, fake_cache)

        context = service.build_context("AAPL")

        peer = context["peer_comparison"]
        assert peer is not None
        assert peer["revenue_rank"] == 2
        assert peer["revenue_total_peers"] == 3
        assert peer["net_income_rank"] == 2
        assert peer["net_income_total_peers"] == 3

    def test_build_context_respects_include_peers_false(self, db_session, fake_cache):
        """When include_peers=False, peer_comparison should be None even if peers exist."""
        self._seed_peers(db_session)
        service = _make_service(db_session, fake_cache)

        context = service.build_context("AAPL", include_peers=False)

        assert context["peer_comparison"] is None

    def test_build_context_peer_comparison_null_when_no_peers(self, db_session, fake_cache):
        """Peer comparison should be null when the sub-industry has one company."""
        company = Company(
            ticker="AAPL",
            cik="0000320193",
            name="Apple Inc.",
            industry=IndustryClassification(gics_sub_industry="Semiconductors"),
        )
        CompanyRepository(db_session).create_or_update(company)
        FinancialsRepository(db_session).save_facts(
            [
                FinancialFact(
                    ticker="AAPL",
                    fiscal_year=2025,
                    fiscal_period="FY",
                    report_date=date(2025, 9, 27),
                    concept="Revenue",
                    value=100.0,
                )
            ]
        )

        service = _make_service(db_session, fake_cache)
        context = service.build_context("AAPL")

        assert context["peer_comparison"] is None

    def test_build_context_peer_comparison_null_without_sub_industry(self, db_session, fake_cache):
        """Peer comparison should be null when the company has no GICS sub-industry."""
        _seed_company_and_facts(db_session)
        service = _make_service(db_session, fake_cache)

        context = service.build_context("AAPL")

        assert context["peer_comparison"] is None


class TestCompanyContextEdgeCases:
    """Edge-case tests for CompanyContextService internals."""

    def test_build_context_creates_company_from_edgar(self, db_session, fake_cache):
        """When company does not exist in DB, service fetches from Edgar and persists it."""
        service = _make_service(
            db_session,
            fake_cache,
            data_source=FakeDataSource(),
        )
        company = service._get_or_create_company("AAPL")

        assert company.ticker == "AAPL"
        assert company.cik == "0000320193"
        assert company.name == "Apple Inc."

        # Company should now be persisted.
        persisted = CompanyRepository(db_session).get_by_ticker("AAPL")
        assert persisted is not None
        assert persisted.cik == "0000320193"

    def test_build_context_missing_cik_raises(self, db_session, fake_cache):
        """Edgar info without a CIK should raise TickerNotFoundError."""
        from omninexu.observability import TickerNotFoundError

        service = _make_service(
            db_session,
            fake_cache,
            data_source=FakeDataSource(
                company_info={"ticker": "UNKNOWN", "cik": "", "name": "Unknown", "sic": ""},
            ),
        )

        with pytest.raises(TickerNotFoundError):
            service.build_context("UNKNOWN")

    def test_build_context_uses_cache(self, db_session, fake_cache):
        """A cached context should be returned directly without hitting the DB."""
        _seed_company_and_facts(db_session)
        service = _make_service(db_session, fake_cache)

        from omninexu.application.company_context import CACHE_VERSION
        context_first = service.build_context("AAPL")
        fake_cache.set_json(f"company_context:{CACHE_VERSION}:AAPL", {"ticker": "CACHED"})

        context_second = service.build_context("AAPL")
        assert context_second["ticker"] == "CACHED"
        assert context_first["ticker"] == "AAPL"

    def test_build_longitudinal_empty_facts(self, db_session, fake_cache):
        """_build_longitudinal should return an empty dict when no facts exist."""
        company = Company(
            ticker="AAPL",
            cik="0000320193",
            name="Apple Inc.",
            industry=IndustryClassification(),
        )
        CompanyRepository(db_session).create_or_update(company)

        service = _make_service(db_session, fake_cache)
        assert service._build_longitudinal("AAPL") == {}

    def test_build_longitudinal_skips_unknown_concept_key(self, db_session, fake_cache, monkeypatch):
        """_build_longitudinal should skip concepts not present in CONCEPT_TO_KEY."""
        company = Company(
            ticker="AAPL",
            cik="0000320193",
            name="Apple Inc.",
            industry=IndustryClassification(),
        )
        CompanyRepository(db_session).create_or_update(company)

        facts = [
            FinancialFact(
                ticker="AAPL",
                fiscal_year=year,
                fiscal_period="FY",
                report_date=date(year, 9, 30),
                concept="Revenue",
                value=float(value),
            )
            for year, value in [(2021, 100), (2022, 110), (2023, 121)]
        ]
        FinancialsRepository(db_session).save_facts(facts)

        # Force Revenue to be processed longitudinally but not mapped to a response key.
        monkeypatch.setattr(
            "omninexu.application.company_context.LONGITUDINAL_CONCEPTS",
            ["Revenue"],
        )
        monkeypatch.setattr(
            "omninexu.application.company_context.CONCEPT_TO_KEY",
            {},
        )

        service = _make_service(db_session, fake_cache)
        result = service._build_longitudinal("AAPL")

        assert result == {}

    def test_build_fundamentals_skips_unknown_concepts(self, db_session, fake_cache):
        """_build_fundamentals should ignore concepts not in CONCEPT_TO_KEY."""
        facts = [
            FinancialFact(
                ticker="AAPL",
                fiscal_year=2025,
                fiscal_period="FY",
                report_date=date(2025, 9, 27),
                concept="SomeUnknownConcept",
                value=123.0,
            )
        ]
        fundamentals = CompanyContextService._build_fundamentals(facts)
        assert fundamentals == {}

    def test_latest_report_date_empty_facts(self):
        """_latest_report_date should return None for an empty fact list."""
        assert CompanyContextService._latest_report_date([]) is None
