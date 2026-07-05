"""SEC filings route handler — recent filing metadata."""
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from omninexu.application.company_context import CompanyContextService
from omninexu.infrastructure.db import get_db
from omninexu.observability import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/company/filings")
async def get_filings(
    ticker: str = Query(..., description="Stock ticker symbol, e.g. AAPL"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Recent SEC filings — 10-K, 10-Q, 8-K, and source references."""
    svc = CompanyContextService(db)
    ctx = svc.build_context(ticker.upper(), include_peers=False)
    return {
        "ticker": ticker.upper(),
        "company_name": ctx.get("name", ""),
        "cik": ctx.get("cik", ""),
        "sources": ctx.get("sources", []),
        "as_of_date": ctx.get("as_of_date"),
    }
