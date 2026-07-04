"""Health check router."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from omninexu.infrastructure.cache import cache
from omninexu.infrastructure.db import get_db
from omninexu.observability import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/health")
async def health_check(db: Session = Depends(get_db)) -> dict[str, str]:
    """Health check endpoint."""
    result = {"status": "ok", "database": "ok", "cache": "ok"}

    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning(f"Health check database failure: {exc}")
        result["database"] = "error"
        result["status"] = "degraded"

    try:
        cache.client.ping()
    except Exception as exc:
        logger.warning(f"Health check cache failure: {exc}")
        result["cache"] = "error"
        result["status"] = "degraded"

    return result
