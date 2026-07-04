"""Tests for x402 payment middleware configuration."""

import pytest

from omninexu.api.middleware.x402 import build_x402_middleware
from omninexu.observability.errors import X402ConfigError


class TestBuildX402Middleware:
    """Unit tests for build_x402_middleware() configuration logic."""

    def test_returns_none_when_disabled(self, monkeypatch) -> None:
        """X402_ENABLED=False returns None (skip middleware registration)."""
        from omninexu.api.middleware.x402 import settings

        monkeypatch.setattr(settings, "x402_enabled", False)
        assert build_x402_middleware() is None

    def test_raises_when_pay_to_empty(self, monkeypatch) -> None:
        """X402_ENABLED=True + empty X402_PAY_TO raises X402ConfigError."""
        from omninexu.api.middleware.x402 import settings

        monkeypatch.setattr(settings, "x402_enabled", True)
        monkeypatch.setattr(settings, "x402_pay_to", "")
        with pytest.raises(X402ConfigError, match="X402_PAY_TO"):
            build_x402_middleware()

    def test_raises_when_network_not_caip2(self, monkeypatch) -> None:
        """Non-CAIP-2 network identifier raises X402ConfigError."""
        from omninexu.api.middleware.x402 import settings

        monkeypatch.setattr(settings, "x402_enabled", True)
        monkeypatch.setattr(settings, "x402_pay_to", "0xTEST")
        monkeypatch.setattr(settings, "x402_network", "base")  # not CAIP-2
        with pytest.raises(X402ConfigError, match="CAIP-2"):
            build_x402_middleware()

    def test_free_route_not_in_routes(self, monkeypatch) -> None:
        """Routes in X402_FREE_ROUTES are excluded from payment config."""
        from omninexu.api.middleware.x402 import settings

        monkeypatch.setattr(settings, "x402_enabled", True)
        monkeypatch.setattr(settings, "x402_pay_to", "0xTEST")
        monkeypatch.setattr(settings, "x402_network", "eip155:84532")
        monkeypatch.setattr(
            settings, "x402_free_routes", ["GET /v1/company/context"]
        )

        routes, _server = build_x402_middleware()  # type: ignore[misc]
        assert "GET /v1/company/context" not in routes


class TestX402MiddlewareIntegration:
    """Integration tests: app behaviour with x402 middleware."""

    def test_health_is_always_free(self, client) -> None:
        """GET /v1/health never requires payment."""
        response = client.get("/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] in ("ok", "degraded")

    def test_root_is_free(self, client) -> None:
        """GET / is not in the paid-routes config."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["name"] == "OmniNexu"
