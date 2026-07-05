"""Smart Money bundle — insider + institutional in one call."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from omninexu.application.insider import build_insider_summary
from omninexu.application.institutional import build_institutional_summary
from omninexu.infrastructure.db import get_db
from omninexu.infrastructure.repositories import (
    InsiderRepository,
    InstitutionalRepository,
)
from omninexu.observability import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/company/smart-money")
async def get_smart_money(
    ticker: str = Query(..., description="Stock ticker symbol, e.g. AAPL"),
    db: Session = Depends(get_db),
) -> dict:
    """Bundled insider trading + institutional holdings in one call."""
    t = ticker.upper()
    insider = build_insider_summary(t, InsiderRepository(db))
    inst = build_institutional_summary(t, InstitutionalRepository(db))
    return {
        "ticker": t,
        "insider": insider,
        "institutional": inst,
    }
