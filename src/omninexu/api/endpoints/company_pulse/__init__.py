
"""Company Pulse endpoint — $0.02."""
from x402.http.types import RouteConfig

from omninexu.api.middleware.x402.discovery_config import ICON_URL, SERVICE_NAME, get_tags
from omninexu.api.middleware.x402.helpers import make_bazaar_extension, make_payment_option

__all__ = ["register"]

ENDPOINT_META = {
    "url": "https://api.omninexu.com/v1/company/pulse",
    "description": (
        "Investment signals for any US-listed stock — insider sentiment, "
        "institutional flow, revenue trend, and recent insider transactions "
        "aggregated into a bullish/bearish rating. "
        "Real SEC EDGAR data, not mock."
    ),
}

_INPUT = {
    "type": "object",
    "properties": {
        "ticker": {"type": "string",
            "description": "US stock ticker (AAPL, MSFT, TSLA). Any US-listed company.",
            "minLength": 1, "maxLength": 5},
    },
    "required": ["ticker"],
}

_OUTPUT = {
    "ticker": "AAPL", "company_name": "Apple Inc.",
    "signal": "bullish", "confidence": "medium",
    "components": {
        "insider_sentiment": "positive",
        "institutional_flow": "accumulation",
        "revenue_trend": "up",
    },
}

_BAZAAR = make_bazaar_extension(
    input_example={"ticker": "AAPL"},
    input_schema=_INPUT, output_example=_OUTPUT,
)


def register(pay_to: str, network: str, free_routes: set[str]) -> dict | None:
    route_key = "GET /v1/company/pulse"
    if route_key in free_routes:
        return None
    return {
        route_key: RouteConfig(
            accepts=[make_payment_option(pay_to, network, "$0.02")],
            resource=ENDPOINT_META["url"],
            mime_type="application/json",
            description=ENDPOINT_META["description"],
            service_name=SERVICE_NAME,
            tags=get_tags("company_pulse"),
            icon_url=ICON_URL,
            extensions=_BAZAAR,
        )
    }
