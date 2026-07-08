"""Financials repository using SQLAlchemy."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from omninexu.domain.financials import FinancialFact
from omninexu.infrastructure.models import CompanyModel, FinancialFactModel
from omninexu.infrastructure.repositories.mappers import (
    financial_fact_model_to_domain,
    financial_fact_to_model,
)
from omninexu.observability import get_logger

logger = get_logger(__name__)


class FinancialsRepository:
    """Data access for financial facts."""

    def __init__(self, db: Session):
        self.db = db

    def get_facts(
        self,
        ticker: str,
        concept: str | None = None,
        fiscal_year: int | None = None,
    ) -> list[FinancialFact]:
        """Get financial facts for a company."""
        ticker_upper = ticker.upper()
        logger.info(f"Getting facts for {ticker_upper}, concept={concept}, year={fiscal_year}")

        stmt = select(FinancialFactModel).where(FinancialFactModel.ticker == ticker_upper)
        if concept is not None:
            stmt = stmt.where(FinancialFactModel.concept == concept)
        if fiscal_year is not None:
            stmt = stmt.where(FinancialFactModel.fiscal_year == fiscal_year)

        stmt = stmt.order_by(
            FinancialFactModel.fiscal_year.desc(),
            FinancialFactModel.concept,
        )

        models = self.db.execute(stmt).scalars().all()
        return [financial_fact_model_to_domain(m) for m in models]

    def get_latest_facts(self, ticker: str) -> list[FinancialFact]:
        """Get facts for the latest fiscal year."""
        ticker_upper = ticker.upper()
        logger.info(f"Getting latest facts for {ticker_upper}")

        latest_year = self._get_latest_fiscal_year(ticker_upper)
        if latest_year is None:
            return []

        return self.get_facts(ticker_upper, fiscal_year=latest_year)

    def get_facts_by_source(
        self,
        ticker: str,
        source: str = "edgar",
        concept: str | None = None,
        fiscal_year: int | None = None,
        fiscal_period: str | None = None,
    ) -> list[FinancialFact]:
        """Get financial facts filtered by data source.

        Args:
            ticker: Stock ticker symbol.
            source: Data source filter — \"edgar\" or \"simfin\".
            concept: Optional concept filter (e.g. \"Revenue\").
            fiscal_year: Optional fiscal year filter.
            fiscal_period: Optional period filter (\"FY\", \"Q1\", \"Q2\", \"Q3\", \"Q4\").

        Returns:
            Matching facts, newest fiscal year first.
        """
        ticker_upper = ticker.upper()
        logger.info(
            f"Getting facts for {ticker_upper}, source={source}, "
            f"concept={concept}, year={fiscal_year}, period={fiscal_period}"
        )

        stmt = (
            select(FinancialFactModel)
            .where(FinancialFactModel.ticker == ticker_upper)
            .where(FinancialFactModel.source == source)
        )
        if concept is not None:
            stmt = stmt.where(FinancialFactModel.concept == concept)
        if fiscal_year is not None:
            stmt = stmt.where(FinancialFactModel.fiscal_year == fiscal_year)
        if fiscal_period is not None:
            stmt = stmt.where(FinancialFactModel.fiscal_period == fiscal_period)

        stmt = stmt.order_by(
            FinancialFactModel.fiscal_year.desc(),
            FinancialFactModel.concept,
        )

        models = self.db.execute(stmt).scalars().all()
        return [financial_fact_model_to_domain(m) for m in models]

    def save_facts(self, facts: list[FinancialFact]) -> None:
        """Save financial facts, upserting on conflict."""
        if not facts:
            return

        logger.info(f"Saving {len(facts)} facts")
        for fact in facts:
            self._save_single_fact(fact)

        self.db.commit()
        logger.info(f"Saved {len(facts)} facts")

    def _save_single_fact(self, fact: FinancialFact) -> None:
        """Persist a single fact, updating if it already exists."""
        ticker_upper = fact.ticker.upper()
        company_id = self._get_company_id(ticker_upper)
        if company_id is None:
            raise ValueError(f"Company not found for ticker: {ticker_upper}")

        existing = self._get_existing_fact(
            company_id,
            fact.fiscal_year,
            fact.fiscal_period,
            fact.concept,
        )

        if existing is None:
            model = financial_fact_to_model(fact, company_id)
            self.db.add(model)
            self.db.flush()  # flush so subsequent lookups see this row
        else:
            existing.value = fact.value
            existing.report_date = fact.report_date
            existing.source_filing = fact.source_filing
            existing.unit = fact.unit
            existing.source = fact.source
            existing.statement_type = fact.statement_type

    def _get_company_id(self, ticker: str) -> int | None:
        """Get company_id for a ticker."""
        model = (
            self.db.execute(select(CompanyModel).where(CompanyModel.ticker == ticker))
            .scalars()
            .first()
        )
        if model is None:
            return None
        return int(model.id)

    def _get_existing_fact(
        self,
        company_id: int,
        fiscal_year: int,
        fiscal_period: str,
        concept: str,
    ) -> FinancialFactModel | None:
        """Find an existing fact by unique key."""
        return (
            self.db.execute(
                select(FinancialFactModel).where(
                    FinancialFactModel.company_id == company_id,
                    FinancialFactModel.fiscal_year == fiscal_year,
                    FinancialFactModel.fiscal_period == fiscal_period,
                    FinancialFactModel.concept == concept,
                )
            )
            .scalars()
            .first()
        )

    def _get_latest_fiscal_year(self, ticker: str) -> int | None:
        """Return the maximum fiscal year for a ticker."""
        result = (
            self.db.execute(
                select(FinancialFactModel.fiscal_year)
                .where(FinancialFactModel.ticker == ticker)
                .order_by(FinancialFactModel.fiscal_year.desc())
            )
            .scalars()
            .first()
        )
        return result
