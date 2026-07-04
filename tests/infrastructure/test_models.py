"""Tests for SQLAlchemy models."""

from datetime import date

import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from omninexu.infrastructure.db import Base
from omninexu.infrastructure.models import (
    CompanyModel,
    FinancialFactModel,
    InsiderTransactionModel,
    InstitutionalHoldingModel,
)


def _in_memory_session():
    """Create an in-memory SQLite session for isolated model tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_models_create_tables():
    """All expected tables should be created."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    tables = inspector.get_table_names()

    assert "companies" in tables
    assert "financial_facts" in tables
    assert "institutional_holdings" in tables
    assert "insider_transactions" in tables


def test_company_crud():
    """Company model can be created and queried."""
    db = _in_memory_session()

    company = CompanyModel(
        ticker="AAPL",
        cik="0000320193",
        name="Apple Inc.",
        sic_code="3571",
        is_snp500=True,
    )
    db.add(company)
    db.commit()

    result = db.execute(select(CompanyModel).where(CompanyModel.ticker == "AAPL")).scalars().first()
    assert result is not None
    assert result.cik == "0000320193"
    assert result.is_snp500 is True


def test_company_default_values():
    """Company defaults are applied correctly."""
    db = _in_memory_session()

    company = CompanyModel(ticker="AAPL", cik="0000320193", name="Apple Inc.")
    db.add(company)
    db.commit()

    assert company.is_snp500 is False
    assert company.created_at is not None
    assert company.updated_at is not None


def test_company_updated_at_changes_on_update():
    """Company updated_at changes after an update."""
    import time

    db = _in_memory_session()

    company = CompanyModel(ticker="AAPL", cik="0000320193", name="Apple Inc.")
    db.add(company)
    db.commit()

    original_updated_at = company.updated_at
    time.sleep(0.01)
    company.name = "Apple Inc. Updated"
    db.commit()

    assert company.updated_at > original_updated_at


def test_financial_fact_crud():
    """Financial fact model can be created and queried."""
    db = _in_memory_session()

    company = CompanyModel(ticker="AAPL", cik="0000320193", name="Apple Inc.")
    db.add(company)
    db.commit()

    fact = FinancialFactModel(
        company_id=company.id,
        ticker="AAPL",
        fiscal_year=2025,
        fiscal_period="FY",
        report_date=date(2025, 9, 27),
        concept="Revenue",
        value=416161000000,
        unit="USD",
        source_filing="10-K",
        statement_type="income",
    )
    db.add(fact)
    db.commit()

    result = (
        db.execute(select(FinancialFactModel).where(FinancialFactModel.ticker == "AAPL"))
        .scalars()
        .first()
    )
    assert result is not None
    assert result.concept == "Revenue"
    assert float(result.value) == 416161000000


def test_financial_fact_unique_constraint():
    """Duplicate financial facts violate the unique constraint."""
    db = _in_memory_session()

    company = CompanyModel(ticker="AAPL", cik="0000320193", name="Apple Inc.")
    db.add(company)
    db.commit()

    fact = FinancialFactModel(
        company_id=company.id,
        ticker="AAPL",
        fiscal_year=2025,
        fiscal_period="FY",
        report_date=date(2025, 9, 27),
        concept="Revenue",
        value=416161000000,
    )
    db.add(fact)
    db.commit()

    duplicate = FinancialFactModel(
        company_id=company.id,
        ticker="AAPL",
        fiscal_year=2025,
        fiscal_period="FY",
        report_date=date(2025, 9, 27),
        concept="Revenue",
        value=123,
    )
    db.add(duplicate)

    with pytest.raises(IntegrityError):
        db.commit()


def test_institutional_holding_crud():
    """Institutional holding model can be created and queried."""
    db = _in_memory_session()

    company = CompanyModel(ticker="AAPL", cik="0000320193", name="Apple Inc.")
    db.add(company)
    db.commit()

    holding = InstitutionalHoldingModel(
        company_id=company.id,
        ticker="AAPL",
        reporting_manager="Berkshire Hathaway Inc",
        cusip="037833100",
        shares=1000000,
        value=200000000,
        report_date=date(2025, 3, 31),
    )
    db.add(holding)
    db.commit()

    result = (
        db.execute(
            select(InstitutionalHoldingModel).where(
                InstitutionalHoldingModel.reporting_manager == "Berkshire Hathaway Inc"
            )
        )
        .scalars()
        .first()
    )
    assert result is not None
    assert result.ticker == "AAPL"
    assert float(result.shares) == 1000000


def test_insider_transaction_crud():
    """Insider transaction model can be created and queried."""
    db = _in_memory_session()

    company = CompanyModel(ticker="AAPL", cik="0000320193", name="Apple Inc.")
    db.add(company)
    db.commit()

    transaction = InsiderTransactionModel(
        company_id=company.id,
        ticker="AAPL",
        insider_name="Tim Cook",
        insider_title="CEO",
        transaction_type="S",
        shares=50000,
        price=175.5,
        transaction_date=date(2025, 4, 1),
    )
    db.add(transaction)
    db.commit()

    result = (
        db.execute(
            select(InsiderTransactionModel).where(
                InsiderTransactionModel.insider_name == "Tim Cook"
            )
        )
        .scalars()
        .first()
    )
    assert result is not None
    assert result.transaction_type == "S"
    assert float(result.price) == 175.5


def test_model_schema_matches_tables():
    """Actual SQLite tables match the model definitions."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    expected = {
        "companies": {
            "id",
            "ticker",
            "cik",
            "name",
            "sic_code",
            "naics_code",
            "gics_sector",
            "gics_industry_group",
            "gics_industry",
            "gics_sub_industry",
            "is_snp500",
            "created_at",
            "updated_at",
        },
        "financial_facts": {
            "id",
            "company_id",
            "ticker",
            "fiscal_year",
            "fiscal_period",
            "report_date",
            "concept",
            "label",
            "value",
            "unit",
            "source_filing",
            "statement_type",
            "source",
            "created_at",
        },
        "institutional_holdings": {
            "id",
            "company_id",
            "ticker",
            "reporting_manager",
            "cusip",
            "shares",
            "value",
            "report_date",
            "source_filing",
            "created_at",
        },
        "insider_transactions": {
            "id",
            "company_id",
            "ticker",
            "insider_name",
            "insider_title",
            "transaction_type",
            "shares",
            "price",
            "transaction_date",
            "created_at",
        },
    }

    for table_name, expected_columns in expected.items():
        actual_columns = {col["name"] for col in inspector.get_columns(table_name)}
        assert actual_columns == expected_columns, (
            f"{table_name} columns mismatch: {actual_columns ^ expected_columns}"
        )

    indexes = inspector.get_indexes("companies")
    index_names = {idx["name"] for idx in indexes}
    assert any("ticker" in name for name in index_names)
    assert any("cik" in name for name in index_names)
