"""Company Pulse endpoint — Quick tier, $0.02."""
from x402.http.types import RouteConfig

from omninexu.api.middleware.x402.helpers import make_payment_option

__all__ = ["register"]

ENDPOINT_META = {
    "url": "https://api.omninexu.com/v1/company/pulse",
    "description": (
        "Investment signals for a ticker: insider sentiment, institutional "
        "flow, revenue trend, and recent insider transactions. "
        "Aggregated bullish/bearish rating."
    ),
}

ICON_URL = "https://api.omninexu.com/static/icon.png"


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
            service_name="OmniNexu",
            tags=["signals", "insider-trading", "institutional-holdings",
                  "revenue-trend", "investment-research"],
            icon_url=ICON_URL,
        )
    }
