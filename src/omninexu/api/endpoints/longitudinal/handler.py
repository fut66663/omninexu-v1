"""Longitudinal CAGR route handler — multi-year growth trends."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from omninexu.application.company_context import CompanyContextService
from omninexu.infrastructure.db import get_db
from omninexu.observability import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/company/longitudinal")
async def get_longitudinal(
    ticker: str = Query(..., description="Stock ticker symbol, e.g. AAPL"),
    db: Session = Depends(get_db),
) -> dict:
    """Multi-year CAGR growth trends for key financial metrics."""
    svc = CompanyContextService(db)
    ctx = svc.build_context(ticker.upper(), include_peers=False)
    longitudinal = ctx.get("longitudinal", {})
    # Format raw CAGR floats as readable percentages
    formatted: dict[str, float] = {}
    for k, v in longitudinal.items():
        formatted[k] = round(v * 100, 1) if k.endswith("_cagr") else round(v, 2)
    return {
        "ticker": ticker.upper(),
        "company_name": ctx.get("name", ""),
        "longitudinal": formatted,
        "as_of_date": ctx.get("as_of_date"),
    }
