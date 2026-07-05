"""Peer ranking route handler — industry comparison only."""
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from omninexu.application.company_context import CompanyContextService
from omninexu.infrastructure.db import get_db
from omninexu.observability import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/company/peer-ranking")
async def get_peer_ranking(
    ticker: str = Query(..., description="Stock ticker to compare"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Industry peer comparison — revenue and net income ranking."""
    svc = CompanyContextService(db)
    ctx = svc.build_context(ticker.upper(), include_peers=True)
    return {
        "ticker": ticker.upper(),
        "company_name": ctx.get("name", ""),
        "peer_comparison": ctx.get("peer_comparison"),
    }
