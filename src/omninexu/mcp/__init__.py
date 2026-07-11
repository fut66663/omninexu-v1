"""MCP server for OmniNexu — pluggable, gated by ``MCP_ENABLED``.

Reuses the existing x402 facilitator and scheme registrations from
``omninexu.api.middleware.x402.server``.  Each HTTP endpoint under
``omninexu.api.endpoints`` is auto-discovered and exposed as a
FastMCP tool with x402 payment gating via ``x402.mcp``.
"""

from .server import create_mcp_server, run_mcp_server

__all__ = ["create_mcp_server", "run_mcp_server"]
