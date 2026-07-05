
"""Smart Money endpoint — Premium tier, $0.05."""
from x402.http.types import RouteConfig

from omninexu.api.middleware.x402.helpers import make_payment_option

from .bazaar import BAZAAR_EXTENSION, ENDPOINT_META
from .handler import router

__all__ = ["router", "register"]

_ICON = "https://api.omninexu.com/static/icon.png"

def register(pay_to: str, network: str, free_routes: set[str]) -> dict | None:
    route_key = "GET /v1/company/smart-money"
    if route_key in free_routes:
        return None
    return {
        route_key: RouteConfig(
            accepts=[make_payment_option(pay_to, network, "$0.05")],
            resource=ENDPOINT_META["url"],
            mime_type="application/json",
            description=ENDPOINT_META["description"],
            service_name="OmniNexu",
            tags=["smart-money", "insider-trading", "13f",
                  "whale-tracking", "hedge-funds"],
            icon_url=_ICON,
            extensions=BAZAAR_EXTENSION,
        )
    }
