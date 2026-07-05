"""Tests for endpoint registry auto-discovery."""

from omninexu.api.middleware.x402.registry import collect_routes


class TestCollectRoutes:
    def test_finds_company_context_endpoint(self):
        routes = collect_routes("0xPAY", "eip155:8453", set())
        assert "GET /v1/company/context" in routes

    def test_excludes_free_routes(self):
        routes = collect_routes(
            "0xPAY", "eip155:8453",
            {"GET /v1/company/context"}
        )
        assert "GET /v1/company/context" not in routes

    def test_returns_empty_dict_when_no_endpoints(self):
        routes = collect_routes("0xPAY", "eip155:8453",
                                 {"GET /v1/company/context"})
        assert isinstance(routes, dict)
        assert "GET /v1/company/context" not in routes
