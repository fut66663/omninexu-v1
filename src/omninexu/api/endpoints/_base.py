"""Endpoint plugin protocol.

Every endpoint directory under ``endpoints/`` must expose a module-level
``register`` callable matching this signature.  The registry auto-discovers
and calls it at startup.
"""
from typing import Protocol

from x402.http.types import RouteConfig


class EndpointPlugin(Protocol):
    """Callable that registers one endpoint's x402 routes."""

    def __call__(
        self, pay_to: str, network: str, free_routes: set[str]
    ) -> dict[str, RouteConfig] | None: ...
