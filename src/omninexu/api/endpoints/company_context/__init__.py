
"""Company Context endpoint — $0.05."""
from x402.http.types import RouteConfig

from omninexu.api.middleware.x402.discovery_config import ICON_URL, SERVICE_NAME, get_tags
from omninexu.api.middleware.x402.helpers import make_payment_option

from .bazaar import BAZAAR_EXTENSION, ENDPOINT_META

__all__ = ["register", "BAZAAR_EXTENSION", "ENDPOINT_META"]


def register(pay_to: str, network: str, free_routes: set[str]) -> dict | None:
    route_key = "GET /v1/company/context"
    if route_key in free_routes:
        return None
    return {
        route_key: RouteConfig(
            accepts=[make_payment_option(pay_to, network, "$0.05")],
            resource=ENDPOINT_META["url"],
            mime_type="application/json",
            description=ENDPOINT_META["description"],
            service_name=SERVICE_NAME,
            tags=get_tags("company_context"),
            icon_url=ICON_URL,
            extensions=BAZAAR_EXTENSION,
        )
    }
