"""x402 payment middleware configuration.

Wraps the official ``PaymentMiddlewareASGI`` with OmniNexu-specific
route definitions and environment-aware toggling.
"""

from typing import Any

from x402.extensions.bazaar import OutputConfig, declare_discovery_extension
from x402.http import (
    CreateHeadersAuthProvider,
    FacilitatorConfig,
    HTTPFacilitatorClient,
    PaymentOption,
)
from x402.http.types import RouteConfig
from x402.mechanisms.evm.exact import ExactEvmServerScheme
from x402.server import x402ResourceServer

from omninexu.config.settings import settings
from omninexu.infrastructure.clients.cdp_auth import create_cdp_auth_headers
from omninexu.observability.errors import X402ConfigError

# CDP Facilitator URL — requires JWT authentication
_CDP_FACILITATOR_URL = "https://api.cdp.coinbase.com/platform/v2/x402"


def _build_facilitator() -> HTTPFacilitatorClient:
    """Build the appropriate Facilitator client.

    Uses JWT auth for CDP Facilitator; no auth for testnet / public.
    """
    url = settings.x402_facilitator_url
    config = FacilitatorConfig(url=url)

    if url == _CDP_FACILITATOR_URL:
        config.auth_provider = CreateHeadersAuthProvider(
            lambda: create_cdp_auth_headers(
                key_id=settings.cdp_api_key_id,
                key_secret=settings.cdp_api_key_secret,
            )
        )

    return HTTPFacilitatorClient(config)


def build_x402_middleware() -> tuple[dict[str, RouteConfig], x402ResourceServer] | None:
    """Build x402 middleware config, or None if payments are disabled.

    Returns a ``(routes, server)`` tuple for
    ``app.add_middleware(PaymentMiddlewareASGI, ...)``.
    Returns None when ``X402_ENABLED`` is False.
    """
    if not settings.x402_enabled:
        return None

    _validate_config()

    facilitator = _build_facilitator()
    server = x402ResourceServer(facilitator)
    server.register(settings.x402_network, ExactEvmServerScheme())  # type: ignore[no-untyped-call]

    routes = _build_routes()
    return routes, server


def _validate_config() -> None:
    """Fast-fail on misconfiguration."""
    if not settings.x402_pay_to:
        raise X402ConfigError(
            "X402_ENABLED=true but X402_PAY_TO is empty"
        )
    if not settings.x402_network.startswith("eip155:"):
        raise X402ConfigError(
            f"X402_NETWORK must be CAIP-2 format (eip155:...), "
            f"got: {settings.x402_network}"
        )


def _build_bazaar_extension() -> dict[str, Any]:
    """Build the Bazaar discovery extension for agentic.market indexing.

    The SDK's ``declare_discovery_extension`` omits the ``method`` field
    (it is injected at runtime by ``bazaar_resource_server_extension``),
    but startup validation requires it.  We patch it in explicitly.
    """
    ext = declare_discovery_extension(
        input={"ticker": "AAPL", "include_peers": True},
        input_schema={
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": (
                        "Stock ticker symbol, e.g. AAPL, MSFT, GOOGL. "
                        "S&P 500 constituents only."
                    ),
                    "minLength": 1,
                    "maxLength": 5,
                },
                "include_peers": {
                    "type": "boolean",
                    "description": (
                        "Include peer ranking within GICS industry group. "
                        "Default: true."
                    ),
                },
            },
            "required": ["ticker"],
        },
        output=OutputConfig(
            example={
                "ticker": "AAPL",
                "company_name": "Apple Inc.",
                "confidence": "high",
                "fundamentals": {
                    "Revenue": 394328000000,
                    "NetIncome": 93736000000,
                    "EPSDiluted": 6.11,
                    "GrossProfit": 180683000000,
                    "OperatingIncome": 123216000000,
                    "TotalAssets": 364980000000,
                    "TotalLiabilities": 308030000000,
                    "StockholdersEquity": 56950000000,
                    "OperatingCashFlow": 118254000000,
                },
                "insider": [
                    {
                        "name": "Timothy D. Cook",
                        "title": "Chief Executive Officer",
                        "transactionType": "Sell",
                        "shares": 10000,
                        "price": 195.0,
                    }
                ],
                "institutional": [
                    {
                        "name": "Vanguard Group",
                        "shares": 1320000000,
                        "value": 225000000000,
                    }
                ],
                "peer_comparison": {
                    "industry": "Technology Hardware, Storage & Peripherals",
                    "revenue_rank": 1,
                    "net_income_rank": 1,
                },
            },
        ),
    )
    # Patch: SDK startup validation requires 'method' in info.input
    ext["bazaar"]["info"]["input"]["method"] = "GET"
    return ext


def _build_routes() -> dict[str, RouteConfig]:
    """Define paid routes with pricing.

    Routes listed in ``X402_FREE_ROUTES`` are excluded from payment
    requirements.  Unlisted routes are NOT automatically paid — only
    routes explicitly defined here require payment.
    """
    pay_to = settings.x402_pay_to
    network = settings.x402_network
    free = set(settings.x402_free_routes)

    all_routes: dict[str, RouteConfig] = {}

    route_key = "GET /v1/company/context"
    if route_key not in free:
        all_routes[route_key] = RouteConfig(
            accepts=[
                PaymentOption(
                    scheme="exact",
                    pay_to=pay_to,
                    price="$0.02",
                    network=network,
                ),
            ],
            resource="https://api.omninexu.com/v1/company/context",
            mime_type="application/json",
            description=(
                "Company Context Quick — fundamentals, confidence, "
                "company info & peer comparison for S&P 500 companies. "
                "Standard tier (insider + institutional) and Pro tier "
                "(longitudinal CAGR) coming soon."
            ),
            service_name="OmniNexu",
            tags=["finance", "sp500", "fundamentals", "sec-edgar"],
            extensions=_build_bazaar_extension(),
        )

    return all_routes
