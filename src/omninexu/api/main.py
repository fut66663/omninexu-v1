"""FastAPI application."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from x402.http.middleware.fastapi import PaymentMiddlewareASGI

from omninexu.api import company_router, health_router
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

app.include_router(health_router, prefix="/v1", tags=["health"])
app.include_router(company_router, prefix="/v1", tags=["company"])

app.middleware("http")(log_request)

# ── x402 Payment Middleware (Phase 0.5) ──
_x402 = build_x402_middleware()
if _x402 is not None:
    routes, server = _x402
    app.add_middleware(PaymentMiddlewareASGI, routes=routes, server=server)


@app.exception_handler(OmniNexuError)
async def omninexu_exception_handler(_: object, exc: OmniNexuError) -> JSONResponse:
    """Handle application errors and return a structured JSON response."""
    logger.warning(f"Application error: {exc.code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.detail,
            }
        },
    )


@app.get("/")
async def root() -> dict[str, str]:
    """Return the service identity and version."""
    return {"name": "OmniNexu", "version": "0.1.0"}
