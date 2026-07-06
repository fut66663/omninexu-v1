"""FastAPI application."""

import os as _os

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from x402.http.middleware.fastapi import PaymentMiddlewareASGI

from omninexu.api import (
    company_router,
    dashboard_router,
    filings_router,
    health_router,
    insider_router,
    institutional_router,
    longitudinal_router,
    peer_ranking_router,
    smart_money_router,
    stats_router,
)
from omninexu.api.middleware.analytics import track_analytics
from omninexu.api.middleware.logging import log_request
from omninexu.api.middleware.x402 import build_x402_middleware
from omninexu.observability.errors import OmniNexuError
from omninexu.observability.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(
    title="OmniNexu API",
    description="AI Agent Decision Context Engine",
    version="0.1.0",
)

# ── Free routes ──
app.include_router(dashboard_router, tags=["dashboard"])
app.include_router(health_router, prefix="/v1", tags=["health"])
app.include_router(stats_router, prefix="/v1", tags=["stats"])
app.include_router(company_router, prefix="/v1", tags=["company"])

# ── Paid endpoint routes ──
app.include_router(filings_router, prefix="/v1", tags=["filings"])
app.include_router(peer_ranking_router, prefix="/v1", tags=["peer-ranking"])
app.include_router(insider_router, prefix="/v1", tags=["insider"])
app.include_router(institutional_router, prefix="/v1", tags=["institutional"])
app.include_router(smart_money_router, prefix="/v1", tags=["smart-money"])
app.include_router(longitudinal_router, prefix="/v1", tags=["longitudinal"])

app.middleware("http")(log_request)
app.middleware("http")(track_analytics)

# ── Static files (icon, etc.) ──
_static_dir = _os.path.join(_os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=_static_dir), name="static")

# ── x402 Payment Middleware ──
_x402 = build_x402_middleware()
if _x402 is not None:
    routes, server = _x402
    app.add_middleware(PaymentMiddlewareASGI, routes=routes, server=server)


@app.exception_handler(OmniNexuError)
async def omninexu_exception_handler(_: object, exc: OmniNexuError) -> JSONResponse:
    logger.warning(f"Application error: {exc.code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.detail}},
    )


@app.on_event("startup")
async def _clear_stale_cache() -> None:
    """Clear old-version cache keys on startup to prevent schema mismatch."""
    try:
        from omninexu.application.company_context import CACHE_VERSION
        from omninexu.infrastructure.cache import cache as _cache

        old_patterns = []
        v = int(CACHE_VERSION.lstrip("v"))
        for old_v in range(1, v):
            old_patterns.append(f"company_context:v{old_v}:*")

        for pattern in old_patterns:
            keys = _cache.client.keys(pattern)
            if keys:
                _cache.client.delete(*keys)
                logger.info(f"Cleared {len(keys)} stale cache keys: {pattern}")
    except Exception:
        pass  # cache clear is best-effort, don't block startup


@app.get("/")
async def root() -> dict[str, str]:
    return {"name": "OmniNexu", "version": "0.1.0"}
