"""Mappers between domain objects and SQLAlchemy models."""

from omninexu.domain.company import Company, IndustryClassification
from omninexu.domain.financials import FinancialFact
from omninexu.domain.insider import InsiderTrade
from omninexu.domain.institutional import InstitutionalHolding
from omninexu.infrastructure.models import (
    CompanyModel,
    FinancialFactModel,
    InsiderTransactionModel,
    InstitutionalHoldingModel,
)


def company_to_model(company: Company) -> CompanyModel:
    """Convert a Company domain object to a CompanyModel."""
    industry = company.industry
    return CompanyModel(
        ticker=company.ticker.upper(),
        cik=company.cik,
        name=company.name,
        sic_code=industry.sic_code,
        naics_code=industry.naics_code,
        gics_sector=industry.gics_sector,
        gics_industry_group=industry.gics_industry_group,
        gics_industry=industry.gics_industry,
        gics_sub_industry=industry.gics_sub_industry,
        is_snp500=company.is_snp500,
    )


def company_model_to_domain(model: CompanyModel) -> Company:
    """Convert a CompanyModel to a Company domain object."""
    return Company(
        ticker=model.ticker,
        cik=model.cik,
        name=model.name,
        industry=IndustryClassification(
            sic_code=model.sic_code,
            naics_code=model.naics_code,
            gics_sector=model.gics_sector,
            gics_industry_group=model.gics_industry_group,
            gics_industry=model.gics_industry,
            gics_sub_industry=model.gics_sub_industry,
        ),
        is_snp500=model.is_snp500,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _update_company_model(model: CompanyModel, company: Company) -> None:
    """Update an existing CompanyModel from a Company domain object."""
    industry = company.industry
    model.cik = company.cik
    model.name = company.name
    model.sic_code = industry.sic_code
    model.naics_code = industry.naics_code
    model.gics_sector = industry.gics_sector
    model.gics_industry_group = industry.gics_industry_group
    model.gics_industry = industry.gics_industry
    model.gics_sub_industry = industry.gics_sub_industry
    model.is_snp500 = company.is_snp500


def financial_fact_to_model(fact: FinancialFact, company_id: int) -> FinancialFactModel:
    """Convert a FinancialFact domain object to a FinancialFactModel."""
    return FinancialFactModel(
        company_id=company_id,
        ticker=fact.ticker.upper(),
        fiscal_year=fact.fiscal_year,
        fiscal_period=fact.fiscal_period,
        report_date=fact.report_date,
        concept=fact.concept,
        value=fact.value,
        unit=fact.unit,
        source_filing=fact.source_filing,
        statement_type=fact.statement_type,
        source=fact.source,
    )


def financial_fact_model_to_domain(model: FinancialFactModel) -> FinancialFact:
    """Convert a FinancialFactModel to a FinancialFact domain object."""
    return FinancialFact(
        ticker=model.ticker,
        fiscal_year=model.fiscal_year,
        fiscal_period=model.fiscal_period,
        report_date=model.report_date,
        concept=model.concept,
        value=float(model.value) if model.value is not None else None,
        unit=model.unit,
        source_filing=model.source_filing,
        statement_type=model.statement_type,
        source=model.source or "simfin",
    )


def update_or_create_company(
    model: CompanyModel | None,
    company: Company,
) -> CompanyModel:
    """Return an updated existing model or a new model from a domain object."""
    if model is None:
        return company_to_model(company)
    _update_company_model(model, company)
    return model


# ── Institutional holdings ────────────────────────────────────────────


def institutional_holding_to_model(
    holding: InstitutionalHolding, company_id: int
) -> InstitutionalHoldingModel:
    """Convert an InstitutionalHolding domain object to a DB model."""
    return InstitutionalHoldingModel(
        company_id=company_id,
        ticker=holding.ticker.upper(),
        reporting_manager=holding.reporting_manager,
        cusip=holding.cusip,
        shares=holding.shares,
        value=holding.value,
        report_date=holding.report_date,
        source_filing=holding.source_filing,
    )


def institutional_holding_model_to_domain(
    model: InstitutionalHoldingModel,
) -> InstitutionalHolding:
    """Convert an InstitutionalHoldingModel to a domain object."""
    return InstitutionalHolding(
        ticker=model.ticker,
        reporting_manager=model.reporting_manager,
        cusip=model.cusip,
        shares=float(model.shares) if model.shares is not None else None,
        value=float(model.value) if model.value is not None else None,
        report_date=model.report_date,
        source_filing=model.source_filing,
    )


# ── Insider transactions ──────────────────────────────────────────────


def insider_trade_to_model(
    trade: InsiderTrade, company_id: int
) -> InsiderTransactionModel:
    """Convert an InsiderTrade domain object to a DB model."""
    return InsiderTransactionModel(
        company_id=company_id,
        ticker=trade.ticker.upper(),
        insider_name=trade.insider_name,
        insider_title=trade.insider_title,
        transaction_type=trade.transaction_type,
        shares=trade.shares,
        price=trade.price,
        transaction_date=trade.transaction_date,
    )


def insider_trade_model_to_domain(
    model: InsiderTransactionModel,
) -> InsiderTrade:
    """Convert an InsiderTransactionModel to a domain object."""
    return InsiderTrade(
        ticker=model.ticker,
        insider_name=model.insider_name or "",
        insider_title=model.insider_title,
        transaction_type=model.transaction_type or "",
        shares=float(model.shares) if model.shares is not None else None,
        price=float(model.price) if model.price is not None else None,
        transaction_date=model.transaction_date,
    )
