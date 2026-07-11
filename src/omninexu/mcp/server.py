"""MCP server — auto-discovers endpoints and exposes them as paid FastMCP tools.

Gated by ``MCP_ENABLED``.  Reuses the shared x402 resource server factory
so facilitator config and scheme registration stay in one place.
"""

from __future__ import annotations

import importlib
import json
import logging
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import CallToolResult, TextContent
from x402.mcp import (
    MCP_PAYMENT_META_KEY,
    MCP_PAYMENT_RESPONSE_META_KEY,
    ResourceInfo,
    SyncPaymentWrapperConfig,
)
from x402.schemas import PaymentPayload, ResourceConfig
from x402.server import x402ResourceServerSync

from omninexu.api.middleware.x402.discovery_config import (
    ICON_URL,
    SERVICE_NAME,
)
from omninexu.api.middleware.x402.server import build_resource_server_sync
from omninexu.config.settings import settings

_logger = logging.getLogger(__name__)

_ENDPOINTS_PKG = "omninexu.api.endpoints"
_ENDPOINTS_DIR = (
    Path(__file__).resolve().parent.parent / "api" / "endpoints"
)


# ── endpoint discovery (same pattern as middleware/x402/registry.py) ──


def _discover_endpoints() -> dict[str, dict[str, Any]]:
    """Return ``{route_key: {price, description, tool_name}}`` for each endpoint."""
    result: dict[str, dict[str, Any]] = {}
    if not _ENDPOINTS_DIR.is_dir():
        return result

    for child in sorted(_ENDPOINTS_DIR.iterdir()):
        if not child.is_dir() or child.name.startswith("_"):
            continue
        try:
            mod = importlib.import_module(f"{_ENDPOINTS_PKG}.{child.name}")
        except ImportError:
            _logger.debug("mcp: skip %s (import failed)", child.name)
            continue

        register = getattr(mod, "register", None)
        if register is None:
            continue

        try:
            routes = register(
                settings.x402_pay_to,
                settings.x402_network,
                set(settings.x402_free_routes),
            )
        except Exception:
            _logger.exception("mcp: %s.register() raised", child.name)
            continue

        if routes:
            for route_key, route_config in routes.items():
                tool_name = _route_to_tool_name(route_key)
                accept = route_config.accepts[0]
                result[route_key] = {
                    "price": accept.price,
                    "scheme": accept.scheme,
                    "network": accept.network,
                    "pay_to": accept.pay_to,
                    "description": route_config.description,
                    "tool_name": tool_name,
                    "tags": route_config.tags,
                }
    return result


def _route_to_tool_name(route_key: str) -> str:
    """``GET /v1/company/context`` → ``company_context``."""
    return route_key.split("/")[-1]


# ── payment helpers ──


def _extract_payment(ctx: Context[Any, Any]) -> dict[str, Any] | None:
    """Pull the x402 payment payload from FastMCP request meta, if present."""
    try:
        request_meta = ctx.request_context.meta
        if request_meta is not None and request_meta.model_extra:
            return request_meta.model_extra.get(MCP_PAYMENT_META_KEY)
    except (AttributeError, ValueError):
        pass
    return None


def _build_payment_required(
    resource_server: x402ResourceServerSync,
    config: SyncPaymentWrapperConfig,
    tool_name: str,
    message: str,
) -> CallToolResult:
    """Return a 402 Payment Required result with full accepts metadata."""
    accepts_dicts: list[dict[str, Any]] = [
        req.model_dump(by_alias=True, exclude_none=True)
        for req in config.accepts
    ]
    resource_url = (
        config.resource.url if config.resource else f"mcp://tool/{tool_name}"
    )
    payment_required: dict[str, Any] = {
        "x402Version": 2,
        "accepts": accepts_dicts,
        "error": message,
        "resource": {
            "url": resource_url,
            "description": config.resource.description if config.resource else None,
        },
    }
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(payment_required))],
        structuredContent=payment_required,
        isError=True,
    )


# ── public API ──


def create_mcp_server() -> FastMCP | None:
    """Build the MCP server, or ``None`` when ``MCP_ENABLED`` is false."""
    if not settings.mcp_enabled:
        _logger.info("mcp: disabled (MCP_ENABLED=false)")
        return None

    resource_server = build_resource_server_sync()
    if resource_server is None:
        _logger.warning("mcp: x402 is disabled, refusing to start")
        return None

    resource_server.initialize()

    endpoints = _discover_endpoints()
    if not endpoints:
        _logger.warning("mcp: no endpoints discovered")
        return None

    mcp: FastMCP = FastMCP(        SERVICE_NAME,
        host="0.0.0.0",
        port=settings.mcp_port,
    )

    paid_count = _register_tools(mcp, resource_server, endpoints)

    # Free health tool — no payment needed
    @mcp.tool()
    def omni_health() -> str:
        """Health check — always free, no payment required."""
        return json.dumps({"status": "ok", "mcp": True, "paid_tools": paid_count})

    _logger.info(
        "mcp: %d paid tool(s) + omni_health registered on :%d",
        paid_count,
        settings.mcp_port,
    )
    return mcp


# ── tool factory (outside the loop to satisfy B023) ──


def _build_tool_fn(
    tool_name: str,
    description: str,
    price: str,
    route_key: str,
    rs: x402ResourceServerSync,
    config: SyncPaymentWrapperConfig,
) -> Any:
    """Return a FastMCP-compatible tool function with x402 payment gating."""

    def tool_fn(ctx: Context[Any, Any], ticker: str = "AAPL") -> CallToolResult:
        payment_data = _extract_payment(ctx)
        if payment_data is None:
            return _build_payment_required(
                rs, config, tool_name,
                "Payment required to access this tool",
            )

        try:
            if isinstance(payment_data, str):
                payment_data = json.loads(payment_data)
            payload = PaymentPayload.model_validate(payment_data)
        except Exception as e:
            return _build_payment_required(
                rs, config, tool_name,
                f"Invalid payment payload: {e}",
            )

        matching = rs.find_matching_requirements(config.accepts, payload)
        if matching is None:
            return _build_payment_required(
                rs, config, tool_name,
                "No matching payment requirements found",
            )

        verify = rs.verify_payment(payload, matching)
        if not verify.is_valid:
            return _build_payment_required(
                rs, config, tool_name,
                f"Payment verification failed: {verify.invalid_reason}",
            )

        settle = rs.settle_payment(payload, matching)
        if not settle.success:
            return _build_payment_required(
                rs, config, tool_name,
                f"Settlement failed: {settle.error_reason}",
            )

        result_data: dict[str, str] = {
            "endpoint": route_key,
            "description": description,
            "price": price,
            "status": "paid_and_settled",
            "tx_hash": settle.transaction or "",
        }
        result_text = json.dumps(result_data)
        response_meta: dict[str, dict[str, Any]] = {
            MCP_PAYMENT_RESPONSE_META_KEY: settle.model_dump(
                by_alias=True, exclude_none=True
            ),
        }
        return CallToolResult(
            content=[TextContent(type="text", text=result_text)],
            isError=False,
            _meta=response_meta,
        )

    return tool_fn


def _register_tools(
    mcp: FastMCP,    resource_server: x402ResourceServerSync,
    endpoints: dict[str, dict[str, Any]],
) -> int:
    """Register one FastMCP tool per endpoint, gated by x402 payment."""
    count = 0
    for route_key, meta in endpoints.items():
        tool_name: str = meta["tool_name"]
        description: str = meta.get("description", "")
        price: str = meta.get("price", "?")

        accepts = resource_server.build_payment_requirements(
            ResourceConfig(
                scheme=meta["scheme"],
                network=meta["network"],
                pay_to=meta["pay_to"],
                price=price,
                extra={"name": "USDC", "version": "2"},
            )
        )

        payment_config = SyncPaymentWrapperConfig(
            accepts=accepts,
            resource=ResourceInfo(
                url=f"mcp://tool/{tool_name}",
                description=description,
                service_name=SERVICE_NAME,
                tags=meta.get("tags"),
                icon_url=ICON_URL,
            ),
        )

        tool_fn = _build_tool_fn(
            tool_name, description, price, route_key,
            resource_server, payment_config,
        )
        tool_fn.__name__ = tool_name
        tool_fn.__doc__ = description

        mcp.tool(name=tool_name, description=description)(tool_fn)
        count += 1

    return count


def run_mcp_server() -> None:
    """Entry point — start the MCP server if ``MCP_ENABLED`` is true."""
    mcp = create_mcp_server()
    if mcp is None:
        _logger.info("mcp: not starting (disabled or no endpoints)")
        return
    mcp.run(transport="sse")
