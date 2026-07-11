"""x402 server wiring — facilitator client and resource server creation."""

from x402.http import (
    CreateHeadersAuthProvider,
    FacilitatorConfig,
    HTTPFacilitatorClient,
    HTTPFacilitatorClientSync,
)
from x402.http.types import RouteConfig
from x402.mechanisms.evm.exact import ExactEvmServerScheme
from x402.server import x402ResourceServer, x402ResourceServerSync

from omninexu.config.settings import settings
from omninexu.infrastructure.clients.cdp_auth import create_cdp_auth_headers
from omninexu.observability.errors import X402ConfigError

from .registry import collect_routes

_CDP_FACILITATOR_URL = "https://api.cdp.coinbase.com/platform/v2/x402"


def build_resource_server() -> x402ResourceServer | None:
    """Build a shared async x402 resource server, or None if payments disabled."""
    if not settings.x402_enabled:
        return None
    _validate_config()
    facilitator = _build_facilitator()
    server = x402ResourceServer(facilitator)
    server.register(settings.x402_network, ExactEvmServerScheme())  # type: ignore[no-untyped-call]
    return server


def build_resource_server_sync() -> x402ResourceServerSync | None:
    """Build a shared sync x402 resource server, or None if payments disabled."""
    if not settings.x402_enabled:
        return None
    _validate_config()
    facilitator = _build_facilitator_sync()
    server = x402ResourceServerSync(facilitator)
    server.register(settings.x402_network, ExactEvmServerScheme())  # type: ignore[no-untyped-call]
    return server


def _build_facilitator_sync() -> HTTPFacilitatorClientSync:
    """Build a sync facilitator client (for FastMCP integration)."""
    url = settings.x402_facilitator_url
    config = FacilitatorConfig(url=url)
    if url == _CDP_FACILITATOR_URL:
        config.auth_provider = CreateHeadersAuthProvider(
            lambda: create_cdp_auth_headers(
                key_id=settings.cdp_api_key_id,
                key_secret=settings.cdp_api_key_secret,
            )
        )
    return HTTPFacilitatorClientSync(config)


def build_x402_middleware() -> tuple[dict[str, RouteConfig], x402ResourceServer] | None:
    """Build x402 HTTP middleware, or None when payments are disabled."""
    server = build_resource_server()
    if server is None:
        return None
    routes = collect_routes(
        settings.x402_pay_to,
        settings.x402_network,
        set(settings.x402_free_routes),
    )
    return routes, server


def _build_facilitator() -> HTTPFacilitatorClient:
    """Build facilitator client. CDP gets JWT auth; testnet/public does not."""
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


def _validate_config() -> None:
    """Fast-fail on misconfiguration."""
    if not settings.x402_pay_to:
        raise X402ConfigError("X402_ENABLED=true but X402_PAY_TO is empty")
    if not settings.x402_network.startswith("eip155:"):
        raise X402ConfigError(
            f"X402_NETWORK must be CAIP-2 format (eip155:...), "
            f"got: {settings.x402_network}"
        )
