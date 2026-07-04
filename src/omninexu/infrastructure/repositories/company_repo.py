"""Company repository using SQLAlchemy."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from omninexu.domain.company import Company
from omninexu.infrastructure.gics_mapping import GicsClassification
from omninexu.infrastructure.models import CompanyModel
from omninexu.infrastructure.repositories.mappers import (
    company_model_to_domain,
    update_or_create_company,
)
from omninexu.observability import get_logger

logger = get_logger(__name__)


class CompanyRepository:
    """Data access for companies."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_ticker(self, ticker: str) -> Company | None:
        """Get company by ticker."""
        ticker_upper = ticker.upper()
        logger.info(f"Getting company by ticker: {ticker_upper}")

        model = self._get_model_by_ticker(ticker_upper)
        if model is None:
            return None

        return company_model_to_domain(model)

    def create_or_update(self, company: Company) -> Company:
        """Create or update company and return the persisted domain object."""
        ticker_upper = company.ticker.upper()
        logger.info(f"Creating or updating company: {ticker_upper}")

        existing = self._get_model_by_ticker(ticker_upper)
        model = update_or_create_company(existing, company)

        self.db.add(model)
        self.db.commit()
        self.db.refresh(model)

        logger.info(f"Company persisted: {ticker_upper}")
        return company_model_to_domain(model)

    def get_by_gics_sub_industry(self, sub_industry: str) -> list[Company]:
        """Get all companies sharing a GICS sub-industry."""
        logger.info(f"Getting companies by GICS sub-industry: {sub_industry}")

        models = (
            self.db.execute(
                select(CompanyModel).where(
                    CompanyModel.gics_sub_industry == sub_industry,
                )
            )
            .scalars()
            .all()
        )
        return [company_model_to_domain(m) for m in models]

    def update_gics(self, ticker: str, gics: GicsClassification) -> None:
        """Update a company's GICS fields from a GicsClassification."""
        ticker_upper = ticker.upper()
        model = self._get_model_by_ticker(ticker_upper)
        if model is None:
            logger.warning(f"Cannot update GICS: ticker not found: {ticker_upper}")
            return

        model.gics_sector = gics.gics_sector
        model.gics_industry_group = gics.gics_industry_group
        model.gics_industry = gics.gics_industry
        model.gics_sub_industry = gics.gics_sub_industry
        self.db.commit()
        logger.info(f"Updated GICS for {ticker_upper}: {gics.gics_sub_industry}")

    def _get_model_by_ticker(self, ticker: str) -> CompanyModel | None:
        """Fetch the raw CompanyModel by ticker."""
        return (
            self.db.execute(select(CompanyModel).where(CompanyModel.ticker == ticker))
            .scalars()
            .first()
        )
