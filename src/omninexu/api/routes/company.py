"""Company router and schemas."""

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from omninexu.api.schemas import CompanyContextResponse
from omninexu.application.company_context import CompanyContextService
from omninexu.infrastructure.db import get_db
from omninexu.infrastructure.product_store import save_product
from omninexu.observability import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/company/context", response_model=CompanyContextResponse)
async def get_company_context(
    background_tasks: BackgroundTasks,
    ticker: str = Query(..., description="Stock ticker symbol"),
    include_peers: bool = Query(True, description="Include peer comparison"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get company context for a ticker."""
    service = CompanyContextService(db)
    context = service.build_context(ticker, include_peers=include_peers)
    background_tasks.add_task(
        save_product, "context", ticker, context
    )
    return context
