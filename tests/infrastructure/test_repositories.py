"""Tests for CompanyRepository, FinancialsRepository, InsiderRepository, and InstitutionalRepository."""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from omninexu.domain.company import Company, IndustryClassification
from omninexu.domain.financials import FinancialFact
from omninexu.domain.insider import InsiderTrade
from omninexu.domain.institutional import InstitutionalHolding
from omninexu.infrastructure.db import Base
from omninexu.infrastructure.models import (
    CompanyModel,
)
from omninexu.infrastructure.repositories import (
    CompanyRepository,
    FinancialsRepository,
    InsiderRepository,
    InstitutionalRepository,
)


@pytest.fixture
def db_session():
    """Create an in-memory SQLite session for repository tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


class TestCompanyRepository:
    """Tests for CompanyRepository."""

    def test_create_company(self, db_session):
        """Repository should create a new company."""
        repo = CompanyRepository(db_session)
        company = Company(
            ticker="AAPL",
            cik="0000320193",
            name="Apple Inc.",
            industry=IndustryClassification(sic_code="3571"),
        )

        result = repo.create_or_update(company)

        assert result.ticker == "AAPL"
        assert result.cik == "0000320193"
        assert db_session.query(CompanyModel).count() == 1

    def test_get_by_ticker(self, db_session):
        """Repository should retrieve a company by ticker."""
        repo = CompanyRepository(db_session)
        company = Company(
            ticker="AAPL",
            cik="0000320193",
            name="Apple Inc.",
            industry=IndustryClassification(),
        )
        repo.create_or_update(company)

        result = repo.get_by_ticker("AAPL")

        assert result is not None
        assert result.name == "Apple Inc."

    def test_create_or_update_updates_existing(self, db_session):
        """Repository should update an existing company."""
        repo = CompanyRepository(db_session)
        original = Company(
            ticker="AAPL",
            cik="0000320193",
            name="Apple Inc.",
            industry=IndustryClassification(),
        )
        repo.create_or_update(original)

        updated = Company(
            ticker="AAPL",
            cik="0000320193",
            name="Apple Inc. Updated",
            industry=IndustryClassification(sic_code="3571"),
        )
        result = repo.create_or_update(updated)

        assert result.name == "Apple Inc. Updated"
        assert result.industry.sic_code == "3571"
        assert db_session.query(CompanyModel).count() == 1

    def test_get_by_ticker_not_found_returns_none(self, db_session):
        """Repository should return None for unknown ticker."""
        repo = CompanyRepository(db_session)
        assert repo.get_by_ticker("UNKNOWN") is None


class TestFinancialsRepository:
    """Tests for FinancialsRepository."""

    def _seed_company(self, db_session, ticker="AAPL"):
        """Helper to seed a company record."""
        company = Company(
            ticker=ticker,
            cik="0000320193",
            name="Apple Inc.",
            industry=IndustryClassification(),
        )
        return CompanyRepository(db_session).create_or_update(company)

    def test_save_facts(self, db_session):
        """Repository should save financial facts."""
        self._seed_company(db_session)
        repo = FinancialsRepository(db_session)

        facts = [
            FinancialFact(
                ticker="AAPL",
                fiscal_year=2025,
                fiscal_period="FY",
                report_date=date(2025, 9, 27),
                concept="Revenue",
                value=416161000000.0,
            )
        ]
        repo.save_facts(facts)

        result = repo.get_facts("AAPL")
        assert len(result) == 1
        assert result[0].concept == "Revenue"

    def test_save_facts_empty_list_returns_early(self, db_session):
        """Saving an empty fact list should return without error."""
        repo = FinancialsRepository(db_session)
        repo.save_facts([])
        assert repo.get_facts("AAPL") == []

    def test_get_facts_filter_by_concept(self, db_session):
        """Repository should filter facts by concept."""
        self._seed_company(db_session)
        repo = FinancialsRepository(db_session)

        facts = [
            FinancialFact(
                ticker="AAPL",
                fiscal_year=2025,
                fiscal_period="FY",
                report_date=date(2025, 9, 27),
                concept="Revenue",
                value=100.0,
            ),
            FinancialFact(
                ticker="AAPL",
                fiscal_year=2025,
                fiscal_period="FY",
                report_date=date(2025, 9, 27),
                concept="NetIncome",
                value=50.0,
            ),
        ]
        repo.save_facts(facts)

        result = repo.get_facts("AAPL", concept="Revenue")
        assert len(result) == 1
        assert result[0].concept == "Revenue"

    def test_get_facts_filter_by_year(self, db_session):
        """Repository should filter facts by fiscal year."""
        self._seed_company(db_session)
        repo = FinancialsRepository(db_session)

        facts = [
            FinancialFact(
                ticker="AAPL",
                fiscal_year=2024,
                fiscal_period="FY",
                report_date=date(2024, 9, 28),
                concept="Revenue",
                value=100.0,
            ),
            FinancialFact(
                ticker="AAPL",
                fiscal_year=2025,
                fiscal_period="FY",
                report_date=date(2025, 9, 27),
                concept="Revenue",
                value=110.0,
            ),
        ]
        repo.save_facts(facts)

        result = repo.get_facts("AAPL", fiscal_year=2025)
        assert len(result) == 1
        assert result[0].fiscal_year == 2025

    def test_upsert_updates_existing_facts(self, db_session):
        """Repository should update existing facts on conflict."""
        self._seed_company(db_session)
        repo = FinancialsRepository(db_session)

        facts = [
            FinancialFact(
                ticker="AAPL",
                fiscal_year=2025,
                fiscal_period="FY",
                report_date=date(2025, 9, 27),
                concept="Revenue",
                value=100.0,
            )
        ]
        repo.save_facts(facts)

        updated_facts = [
            FinancialFact(
                ticker="AAPL",
                fiscal_year=2025,
                fiscal_period="FY",
                report_date=date(2025, 9, 27),
                concept="Revenue",
                value=200.0,
            )
        ]
        repo.save_facts(updated_facts)

        result = repo.get_facts("AAPL", concept="Revenue")
        assert len(result) == 1
        assert result[0].value == 200.0

    def test_get_latest_facts(self, db_session):
        """Repository should return facts for the latest fiscal year."""
        self._seed_company(db_session)
        repo = FinancialsRepository(db_session)

        facts = [
            FinancialFact(
                ticker="AAPL",
                fiscal_year=2024,
                fiscal_period="FY",
                report_date=date(2024, 9, 28),
                concept="Revenue",
                value=100.0,
            ),
            FinancialFact(
                ticker="AAPL",
                fiscal_year=2025,
                fiscal_period="FY",
                report_date=date(2025, 9, 27),
                concept="Revenue",
                value=110.0,
            ),
            FinancialFact(
                ticker="AAPL",
                fiscal_year=2025,
                fiscal_period="FY",
                report_date=date(2025, 9, 27),
                concept="NetIncome",
                value=50.0,
            ),
        ]
        repo.save_facts(facts)

        result = repo.get_latest_facts("AAPL")
        assert len(result) == 2
        assert all(f.fiscal_year == 2025 for f in result)

    def test_save_facts_for_missing_company_raises(self, db_session):
        """Saving facts for a company that does not exist should raise."""
        repo = FinancialsRepository(db_session)
        facts = [
            FinancialFact(
                ticker="UNKNOWN",
                fiscal_year=2025,
                fiscal_period="FY",
                report_date=date(2025, 9, 27),
                concept="Revenue",
                value=100.0,
            )
        ]

        with pytest.raises(ValueError):
            repo.save_facts(facts)


class TestEndToEndRepository:
    """End-to-end tests for the repository data flow."""

    def test_seed_and_query_aapl_facts(self, db_session):
        """Save AAPL-like facts and verify they can be queried accurately."""
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
            ),
            FinancialFact(
                ticker="AAPL",
                fiscal_year=2025,
                fiscal_period="FY",
                report_date=date(2025, 9, 27),
                concept="NetIncome",
                value=112_010_000_000.0,
            ),
        ]
        fin_repo.save_facts(facts)

        result = fin_repo.get_facts("AAPL", concept="Revenue")
        assert len(result) == 1
        assert result[0].value == 416_161_000_000.0

        latest = fin_repo.get_latest_facts("AAPL")
        assert len(latest) == 2


class TestInsiderRepository:
    """Tests for InsiderRepository."""

    def _seed_company(self, db_session, ticker="AAPL"):
        """Helper to seed a company record."""
        company = Company(
            ticker=ticker,
            cik="0000320193",
            name="Apple Inc.",
            industry=IndustryClassification(),
        )
        return CompanyRepository(db_session).create_or_update(company)

    def test_save_trades_unknown_company_returns_early(self, db_session):
        """save_trades() should return early (no-op) when company not found (line 30-31)."""
        repo = InsiderRepository(db_session)
        trades = [
            InsiderTrade(
                ticker="UNKNOWN",
                insider_name="John Doe",
                insider_title="Officer",
                transaction_type="S",
                shares=1000.0,
                price=195.0,
                transaction_date=date(2025, 6, 15),
                source_filing="ACC-001",
            )
        ]
        # Should not raise, just log a warning and return
        repo.save_trades("UNKNOWN", trades)
        assert repo.get_trades("UNKNOWN") == []

    def test_save_and_get_trades(self, db_session):
        """save_trades() should persist and get_trades() should retrieve."""
        self._seed_company(db_session, "AAPL")
        repo = InsiderRepository(db_session)

        trades = [
            InsiderTrade(
                ticker="AAPL",
                insider_name="Tim Cook",
                insider_title="CEO",
                transaction_type="S",
                shares=10000.0,
                price=195.0,
                transaction_date=date.today(),
                source_filing="ACC-001",
            ),
            InsiderTrade(
                ticker="AAPL",
                insider_name="Arthur Levinson",
                insider_title="Chair",
                transaction_type="P",
                shares=5000.0,
                price=190.0,
                transaction_date=date.today(),
                source_filing="ACC-002",
            ),
        ]
        repo.save_trades("AAPL", trades)

        result = repo.get_trades("AAPL")
        assert len(result) == 2
        assert result[0].ticker == "AAPL"

    def test_save_trades_overwrites_previous(self, db_session):
        """Second save_trades() should replace all previous trades for that ticker."""
        self._seed_company(db_session, "AAPL")
        repo = InsiderRepository(db_session)

        old_trades = [
            InsiderTrade(
                ticker="AAPL", insider_name="Old", insider_title="X",
                transaction_type="S", shares=1.0, price=1.0,
                transaction_date=date(2025, 1, 1), source_filing="OLD",
            )
        ]
        repo.save_trades("AAPL", old_trades)

        new_trades = [
            InsiderTrade(
                ticker="AAPL", insider_name="New", insider_title="Y",
                transaction_type="P", shares=2.0, price=2.0,
                transaction_date=date.today(), source_filing="NEW",
            )
        ]
        repo.save_trades("AAPL", new_trades)

        result = repo.get_trades("AAPL")
        assert len(result) == 1
        assert result[0].insider_name == "New"


class TestInstitutionalRepository:
    """Tests for InstitutionalRepository."""

    def _seed_company(self, db_session, ticker="AAPL"):
        """Helper to seed a company record."""
        company = Company(
            ticker=ticker,
            cik="0000320193",
            name="Apple Inc.",
            industry=IndustryClassification(),
        )
        return CompanyRepository(db_session).create_or_update(company)

    def test_save_holdings_unknown_company_returns_early(self, db_session):
        """save_holdings() should return early when company not found (line 28-29)."""
        repo = InstitutionalRepository(db_session)
        holdings = [
            InstitutionalHolding(
                ticker="UNKNOWN",
                reporting_manager="Vanguard",
                shares=1000000.0,
                value=50000000.0,
                report_date=date(2025, 3, 31),
                source_filing="ACC-001",
            )
        ]
        # Should not raise, just log a warning and return
        repo.save_holdings("UNKNOWN", holdings)
        assert repo.get_holdings("UNKNOWN") == []

    def test_save_and_get_holdings(self, db_session):
        """save_holdings() should persist and get_holdings() should retrieve."""
        self._seed_company(db_session, "AAPL")
        repo = InstitutionalRepository(db_session)

        holdings = [
            InstitutionalHolding(
                ticker="AAPL",
                reporting_manager="Vanguard",
                shares=1_000_000.0,
                value=50_000_000.0,
                report_date=date(2025, 3, 31),
                source_filing="ACC-001",
            ),
            InstitutionalHolding(
                ticker="AAPL",
                reporting_manager="BlackRock",
                shares=800_000.0,
                value=40_000_000.0,
                report_date=date(2025, 3, 31),
                source_filing="ACC-002",
            ),
        ]
        repo.save_holdings("AAPL", holdings)

        result = repo.get_holdings("AAPL")
        assert len(result) == 2
        # Should be sorted by value descending
        assert result[0].reporting_manager == "Vanguard"
        assert result[1].reporting_manager == "BlackRock"

    def test_save_holdings_overwrites_previous(self, db_session):
        """Second save_holdings() should replace all previous holdings for that ticker."""
        self._seed_company(db_session, "AAPL")
        repo = InstitutionalRepository(db_session)

        old_holdings = [
            InstitutionalHolding(
                ticker="AAPL", reporting_manager="Old Fund",
                shares=1.0, value=1.0, report_date=date(2025, 1, 1),
                source_filing="OLD",
            )
        ]
        repo.save_holdings("AAPL", old_holdings)

        new_holdings = [
            InstitutionalHolding(
                ticker="AAPL", reporting_manager="New Fund",
                shares=2.0, value=2.0, report_date=date(2025, 3, 31),
                source_filing="NEW",
            )
        ]
        repo.save_holdings("AAPL", new_holdings)

        result = repo.get_holdings("AAPL")
        assert len(result) == 1
        assert result[0].reporting_manager == "New Fund"
