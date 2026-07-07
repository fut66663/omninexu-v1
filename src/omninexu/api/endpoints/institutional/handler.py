
"""Institutional holdings route handler."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from omninexu.application.institutional import build_institutional_summary
from omninexu.infrastructure.db import get_db
from omninexu.infrastructure.repositories import InstitutionalRepository
from omninexu.observability import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/company/institutional")
async def get_institutional(
    ticker: str = Query(..., description="Stock ticker symbol, e.g. AAPL, MSFT"),
    db: Session = Depends(get_db),
) -> dict:
    """SEC 13F institutional holdings — top holders ranked by value."""
    repo = InstitutionalRepository(db)
    result = build_institutional_summary(ticker.upper(), repo)
    if result is None:
        return {"ticker": ticker.upper(), "top_holders": [],
                "message": "No institutional holdings data found"}
    return {"ticker": ticker.upper(), **result.model_dump()}
