"""Entry point for ``python -m omninexu.mcp``.

Requires ``MCP_ENABLED=true`` and ``X402_ENABLED=true`` in the environment.
Starts the FastMCP SSE server on ``MCP_PORT`` (default 4022).
"""

from omninexu.mcp import run_mcp_server

if __name__ == "__main__":
    run_mcp_server()
