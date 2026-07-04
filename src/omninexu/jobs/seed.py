"""Data seeding utilities."""

from sqlalchemy.orm import Session

from omninexu.domain.company import Company, IndustryClassification
from omninexu.domain.datasource import CompanyDataSource
from omninexu.infrastructure.clients import EdgarClient
from omninexu.infrastructure.repositories import (
    CompanyRepository,
    FinancialsRepository,
)
from omninexu.observability import get_logger

logger = get_logger(__name__)


def seed_company(
    db: Session,
    ticker: str,
    cik: str,
    name: str,
    sic: str | None = None,
) -> Company:
    """Seed a single company record."""
    repo = CompanyRepository(db)
    company = Company(
        ticker=ticker,
        cik=cik,
        name=name,
        industry=IndustryClassification(sic_code=sic),
    )
    persisted = repo.create_or_update(company)
    logger.info(f"Seeded company: {ticker}")
    return persisted


def seed_company_financials(
    db: Session,
    ticker: str,
    data_source: CompanyDataSource | None = None,
) -> None:
    """Seed latest 10-K financial facts for a company.

    Args:
        data_source: Any :class:`CompanyDataSource` implementation.
            Defaults to ``EdgarClient`` (SEC EDGAR).
    """
    client = data_source or EdgarClient()
    repo = FinancialsRepository(db)

    facts = client.get_financial_facts(ticker)
    if not facts:
        logger.warning(f"No financial facts found for {ticker}")
        return

    repo.save_facts(facts)
    logger.info(f"Seeded {len(facts)} financial facts for {ticker}")


def seed_quarterly_financials(
    db: Session,
    ticker: str,
    num_quarters: int = 4,
) -> None:
    """Seed latest 10-Q quarterly financial facts for a company.

    Downloads *num_quarters* latest 10-Q filings from SEC EDGAR,
    parses them into :class:`FinancialFact` objects, and saves to the
    database with ``source="edgar"``.

    Quarterly facts use ``fiscal_period`` ∈ {Q1, Q2, Q3} and are
    isolated from annual (``fiscal_period="FY"``) facts via the
    unique constraint on (company_id, fiscal_year, fiscal_period, concept).

    Args:
        num_quarters: Number of latest 10-Q filings to download.
            Default ``4`` (covers ~1 year of quarters).
    """
    client = EdgarClient()
    repo = FinancialsRepository(db)

    facts = client.get_financial_facts(
        ticker, num_filings=num_quarters, form="10-Q"
    )
    if not facts:
        logger.warning(f"No 10-Q financial facts found for {ticker}")
        return

    repo.save_facts(facts)
    logger.info(
        f"Seeded {len(facts)} quarterly facts for {ticker} "
        f"({num_quarters} 10-Q filings)"
    )
