"""Tests for repository mappers."""

from datetime import date, datetime

from omninexu.domain.company import Company, IndustryClassification
from omninexu.domain.financials import FinancialFact
from omninexu.infrastructure.models import CompanyModel, FinancialFactModel
from omninexu.infrastructure.repositories.mappers import (
    company_model_to_domain,
    company_to_model,
    financial_fact_model_to_domain,
    financial_fact_to_model,
    update_or_create_company,
)


def test_company_to_model_maps_all_fields():
    """All Company fields should be mapped to CompanyModel."""
    company = Company(
        ticker="AAPL",
        cik="0000320193",
        name="Apple Inc.",
        industry=IndustryClassification(
            sic_code="3571",
            naics_code="334111",
            gics_sector="Information Technology",
            gics_industry_group="Technology Hardware & Equipment",
            gics_industry="Technology Hardware, Storage & Peripherals",
            gics_sub_industry="Technology Hardware, Storage & Peripherals",
        ),
        is_snp500=True,
    )

    model = company_to_model(company)

    assert model.ticker == "AAPL"
    assert model.cik == "0000320193"
    assert model.name == "Apple Inc."
    assert model.sic_code == "3571"
    assert model.naics_code == "334111"
    assert model.is_snp500 is True


def test_company_model_to_domain_maps_all_fields():
    """All CompanyModel fields should be mapped to Company domain object."""
    model = CompanyModel(
        ticker="AAPL",
        cik="0000320193",
        name="Apple Inc.",
        sic_code="3571",
        naics_code="334111",
        is_snp500=True,
    )
    model.created_at = datetime(2025, 1, 1, 12, 0, 0)
    model.updated_at = datetime(2025, 1, 1, 12, 0, 0)

    company = company_model_to_domain(model)

    assert company.ticker == "AAPL"
    assert company.cik == "0000320193"
    assert company.name == "Apple Inc."
    assert company.industry.sic_code == "3571"
    assert company.industry.naics_code == "334111"
    assert company.is_snp500 is True
    assert company.created_at == model.created_at


def test_company_roundtrip_preserves_data():
    """Mapping to model and back should preserve all data."""
    original = Company(
        ticker="MSFT",
        cik="0000789019",
        name="Microsoft Corp",
        industry=IndustryClassification(sic_code="7372"),
    )

    model = company_to_model(original)
    result = company_model_to_domain(model)

    assert result.ticker == original.ticker
    assert result.cik == original.cik
    assert result.name == original.name
    assert result.industry.sic_code == original.industry.sic_code
    assert result.is_snp500 == original.is_snp500


def test_financial_fact_to_model_maps_all_fields():
    """All FinancialFact fields should be mapped to FinancialFactModel."""
    fact = FinancialFact(
        ticker="AAPL",
        fiscal_year=2025,
        fiscal_period="FY",
        report_date=date(2025, 9, 27),
        concept="Revenue",
        value=416161000000.0,
        unit="USD",
        source_filing="10-K",
        statement_type="income",
    )

    model = financial_fact_to_model(fact, company_id=1)

    assert model.company_id == 1
    assert model.ticker == "AAPL"
    assert model.fiscal_year == 2025
    assert model.fiscal_period == "FY"
    assert model.concept == "Revenue"
    assert float(model.value) == 416161000000.0
    assert model.unit == "USD"
    assert model.source_filing == "10-K"
    assert model.statement_type == "income"


def test_financial_fact_model_to_domain_maps_all_fields():
    """All FinancialFactModel fields should be mapped to FinancialFact."""
    model = FinancialFactModel(
        company_id=1,
        ticker="AAPL",
        fiscal_year=2025,
        fiscal_period="FY",
        report_date=date(2025, 9, 27),
        concept="Revenue",
        value=416161000000.0,
        unit="USD",
        source_filing="10-K",
    )

    fact = financial_fact_model_to_domain(model)

    assert fact.ticker == "AAPL"
    assert fact.fiscal_year == 2025
    assert fact.fiscal_period == "FY"
    assert fact.concept == "Revenue"
    assert fact.value == 416161000000.0
    assert fact.unit == "USD"


def test_update_or_create_company_creates_new_model():
    """update_or_create_company should create a new model when none exists."""
    company = Company(
        ticker="AAPL",
        cik="0000320193",
        name="Apple Inc.",
        industry=IndustryClassification(),
    )

    model = update_or_create_company(None, company)

    assert model.ticker == "AAPL"
    assert model.cik == "0000320193"


def test_update_or_create_company_updates_existing_model():
    """update_or_create_company should update an existing model."""
    existing = CompanyModel(ticker="AAPL", cik="old", name="Old Name")
    company = Company(
        ticker="AAPL",
        cik="0000320193",
        name="Apple Inc.",
        industry=IndustryClassification(),
    )

    model = update_or_create_company(existing, company)

    assert model is existing
    assert model.cik == "0000320193"
    assert model.name == "Apple Inc."
