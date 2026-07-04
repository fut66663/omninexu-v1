"""Institutional holdings repository."""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from omninexu.domain.institutional import InstitutionalHolding
from omninexu.infrastructure.models import CompanyModel, InstitutionalHoldingModel
from omninexu.infrastructure.repositories.mappers import (
    institutional_holding_model_to_domain,
    institutional_holding_to_model,
)
from omninexu.observability import get_logger

logger = get_logger(__name__)


class InstitutionalRepository:
    """Data access for 13F institutional holdings."""

    def __init__(self, db: Session):
        self.db = db

    def save_holdings(self, ticker: str, holdings: list[InstitutionalHolding]) -> None:
        """Replace all holdings for a ticker with new data (13F refresh)."""
        t = ticker.upper()
        company_id = self._get_company_id(t)
        if company_id is None:
            logger.warning(f"Cannot save holdings: company not found: {t}")
            return

        # Delete old data, insert fresh
        self.db.execute(
            delete(InstitutionalHoldingModel).where(InstitutionalHoldingModel.ticker == t)
        )
        for h in holdings:
            self.db.add(institutional_holding_to_model(h, company_id))
        self.db.commit()
        logger.info(f"Saved {len(holdings)} holdings for {t}")

    def get_holdings(self, ticker: str) -> list[InstitutionalHolding]:
        """Get all holdings for a ticker, sorted by value descending."""
        t = ticker.upper()
        models = (
            self.db.execute(
                select(InstitutionalHoldingModel)
                .where(InstitutionalHoldingModel.ticker == t)
                .order_by(InstitutionalHoldingModel.value.desc().nulls_last())
            )
            .scalars()
            .all()
        )
        return [institutional_holding_model_to_domain(m) for m in models]

    def _get_company_id(self, ticker: str) -> int | None:
        model = (
            self.db.execute(
                select(CompanyModel.id).where(CompanyModel.ticker == ticker)
            )
            .scalars()
            .first()
        )
        return model
