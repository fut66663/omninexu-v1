"""x402 Discovery endpoint — /.well-known/x402

AI agents hit this to discover available data products and payment info
before deciding which endpoint to buy.
"""

from typing import Any

from fastapi import APIRouter

from omninexu.config.settings import settings

router = APIRouter()

# ── product catalog ──────────────────────────────────────────

_ENDPOINTS: list[dict[str, Any]] = [
    {
        "path": "/v1/company/context",
        "method": "GET",
        "price": "$0.02",
        "description": "Company fundamentals (9 metrics) + peer comparison + confidence score",
        "parameters": {"ticker": "AAPL"},
    },
    {
        "path": "/v1/company/filings",
        "method": "GET",
        "price": "$0.01",
        "description": "Recent SEC filings — 10-K, 10-Q, 8-K with source URLs",
        "parameters": {"ticker": "AAPL"},
    },
    {
        "path": "/v1/company/peer-ranking",
        "method": "GET",
        "price": "$0.01",
        "description": "Industry peer ranking — revenue & net income position",
        "parameters": {"ticker": "AAPL"},
    },
    {
        "path": "/v1/company/insider",
        "method": "GET",
        "price": "$0.03",
        "description": "SEC Form 4 insider transactions — executive buys/sells",
        "parameters": {"ticker": "AAPL"},
    },
    {
        "path": "/v1/company/institutional",
        "method": "GET",
        "price": "$0.03",
        "description": "SEC 13F institutional holdings — top fund positions",
        "parameters": {"ticker": "AAPL"},
    },
    {
        "path": "/v1/company/smart-money",
        "method": "GET",
        "price": "$0.05",
        "description": "Bundle: insider trades + institutional holdings in one call",
        "parameters": {"ticker": "AAPL"},
    },
    {
        "path": "/v1/company/longitudinal",
        "method": "GET",
        "price": "$0.05",
        "description": "Multi-year CAGR trends — revenue, net income, EPS, cash flow",
        "parameters": {"ticker": "AAPL"},
    },
]


# ── endpoint ─────────────────────────────────────────────────

@router.get("/.well-known/x402")
async def well_known_x402() -> dict[str, Any]:
    return {
        "name": "OmniNexu",
        "description": "AI Agent Decision Context Engine — structured, "
                       "traceable financial intelligence for AI agents",
        "version": "0.1.0",
        "docs": "https://api.omninexu.com/docs",
        "payment": {
            "scheme": "exact",
            "network": settings.x402_network,
            "currency": "USDC",
            "pay_to": settings.x402_pay_to,
            "facilitator": "CDP (Coinbase Developer Platform)",
            "note": "Buyer pays zero gas — CDP Facilitator sponsors on-chain fees",
        },
        "health": "/v1/health",
        "free_routes": settings.x402_free_routes,
        "endpoints": _ENDPOINTS,
    }
