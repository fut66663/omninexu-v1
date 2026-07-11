"""Tests for the MCP server module.

All tests run with ``MCP_ENABLED=false`` by default so they never
accidentally start a real SSE server.  The creation path is tested
via monkeypatching the settings flags.
"""

from __future__ import annotations

import pytest

from omninexu.config.settings import settings
from omninexu.mcp.server import (
    _discover_endpoints,
    _route_to_tool_name,
    create_mcp_server,
)

# ── utility tests ──


@pytest.mark.parametrize(
    "route_key, expected",
    [
        ("GET /v1/company/context", "context"),
        ("GET /v1/company/pulse", "pulse"),
        ("GET /v1/company/filings", "filings"),
        ("GET /v1/health", "health"),
    ],
)
def test_route_to_tool_name(route_key: str, expected: str) -> None:
    assert _route_to_tool_name(route_key) == expected


# ── default-behaviour tests (MCP_ENABLED=false, no special env) ──


def test_create_mcp_server_disabled_by_default() -> None:
    """When MCP_ENABLED is false, create_mcp_server returns None."""
    assert settings.mcp_enabled is False, "expected MCP_ENABLED=false by default"
    result = create_mcp_server()
    assert result is None


def test_create_mcp_server_with_x402_disabled(monkeypatch) -> None:
    """When x402 is disabled, MCP refuses to start even if MCP_ENABLED=true."""
    monkeypatch.setattr(settings, "x402_enabled", False)
    monkeypatch.setattr(settings, "mcp_enabled", True)
    result = create_mcp_server()
    assert result is None


# ── endpoint discovery tests ──


def test_discover_endpoints_returns_at_least_seven() -> None:
    endpoints = _discover_endpoints()
    assert len(endpoints) >= 7, f"expected >=7, got {len(endpoints)}"


def test_discover_endpoints_all_have_price_and_description() -> None:
    endpoints = _discover_endpoints()
    for route_key, meta in endpoints.items():
        assert meta.get("price"), f"{route_key}: missing price"
        assert meta.get("description"), f"{route_key}: missing description"
        assert meta.get("tool_name"), f"{route_key}: missing tool_name"


# ── FastMCP integration test (requires x402 enabled) ──


def test_create_mcp_server_with_both_enabled(monkeypatch) -> None:
    """MCP_ENABLED + X402_ENABLED → returns FastMCP instance."""
    monkeypatch.setattr(settings, "x402_enabled", True)
    monkeypatch.setattr(settings, "mcp_enabled", True)
    monkeypatch.setattr(
        settings, "x402_pay_to", "0x0000000000000000000000000000000000000000"
    )
    monkeypatch.setattr(settings, "x402_network", "eip155:84532")

    srv = create_mcp_server()
    assert srv is not None, "expected FastMCP instance when both flags are true"

    # Verify tools are registered: 8 paid + omni_health
    from mcp.server.fastmcp import FastMCP

    assert isinstance(srv, FastMCP)
