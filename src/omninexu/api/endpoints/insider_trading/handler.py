
"""Insider trading route handler."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from omninexu.application.insider import build_insider_summary
from omninexu.infrastructure.db import get_db
from omninexu.infrastructure.repositories import InsiderRepository
from omninexu.observability import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/company/insider")
async def get_insider(
    ticker: str = Query(..., description="Stock ticker symbol, e.g. AAPL, MSFT"),
    db: Session = Depends(get_db),
) -> dict:
    """SEC Form 4 insider trading — executive buy/sell transactions."""
    repo = InsiderRepository(db)
    result = build_insider_summary(ticker.upper(), repo)
    if result is None:
        return {"ticker": ticker.upper(), "transactions": [],
                "message": "No insider trading data found"}
    return {"ticker": ticker.upper(), **result.model_dump()}
