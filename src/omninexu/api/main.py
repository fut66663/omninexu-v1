"""FastAPI application."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from x402.http.middleware.fastapi import PaymentMiddlewareASGI

from omninexu.api import (
    company_router,
    filings_router,
    health_router,
    insider_router,
    institutional_router,
    longitudinal_router,
    peer_ranking_router,
    smart_money_router,
)
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
app.include_router(health_router, prefix="/v1", tags=["health"])
app.include_router(company_router, prefix="/v1", tags=["company"])

# ── Paid endpoint routes ──
app.include_router(filings_router, prefix="/v1", tags=["filings"])
app.include_router(peer_ranking_router, prefix="/v1", tags=["peer-ranking"])
app.include_router(insider_router, prefix="/v1", tags=["insider"])
app.include_router(institutional_router, prefix="/v1", tags=["institutional"])
app.include_router(smart_money_router, prefix="/v1", tags=["smart-money"])
app.include_router(longitudinal_router, prefix="/v1", tags=["longitudinal"])

app.middleware("http")(log_request)

# ── Static files (icon, etc.) ──
import os as _os

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


@app.get("/")
async def root() -> dict[str, str]:
    return {"name": "OmniNexu", "version": "0.1.0"}
