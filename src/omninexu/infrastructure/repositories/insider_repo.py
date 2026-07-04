"""Insider transactions repository (Form 4 data)."""

from datetime import date, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from omninexu.domain.insider import InsiderTrade
from omninexu.infrastructure.models import CompanyModel, InsiderTransactionModel
from omninexu.infrastructure.repositories.mappers import (
    insider_trade_model_to_domain,
    insider_trade_to_model,
)
from omninexu.observability import get_logger

logger = get_logger(__name__)


class InsiderRepository:
    """Data access for Form 4 insider transactions."""

    def __init__(self, db: Session):
        self.db = db

    def save_trades(self, ticker: str, trades: list[InsiderTrade]) -> None:
        """Replace all trades for a ticker with new data."""
        t = ticker.upper()
        company_id = self._get_company_id(t)
        if company_id is None:
            logger.warning(f"Cannot save trades: company not found: {t}")
            return

        self.db.execute(
            delete(InsiderTransactionModel).where(
                InsiderTransactionModel.ticker == t
            )
        )
        for trade in trades:
            self.db.add(insider_trade_to_model(trade, company_id))
        self.db.commit()
        logger.info(f"Saved {len(trades)} insider trades for {t}")

    def get_trades(self, ticker: str, days: int = 90) -> list[InsiderTrade]:
        """Get trades in the last *days* days, newest first."""
        t = ticker.upper()
        since = date.today() - timedelta(days=days)

        models = (
            self.db.execute(
                select(InsiderTransactionModel)
                .where(InsiderTransactionModel.ticker == t)
                .where(InsiderTransactionModel.transaction_date >= since)
                .order_by(InsiderTransactionModel.transaction_date.desc())
            )
            .scalars()
            .all()
        )
        return [insider_trade_model_to_domain(m) for m in models]

    def _get_company_id(self, ticker: str) -> int | None:
        model = (
            self.db.execute(
                select(CompanyModel.id).where(CompanyModel.ticker == ticker)
            )
            .scalars()
            .first()
        )
        return model
