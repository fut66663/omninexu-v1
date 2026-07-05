"""Tests for company_context endpoint x402 registration."""

from omninexu.api.endpoints.company_context import register


class TestCompanyContextRegister:
    def test_registers_route_key(self):
        routes = register("0xPAY", "eip155:8453", set())
        assert routes is not None
        assert "GET /v1/company/context" in routes

    def test_skips_when_free(self):
        routes = register("0xPAY", "eip155:8453",
                          {"GET /v1/company/context"})
        assert routes is None

    def test_service_name_set(self):
        routes = register("0xPAY", "eip155:8453", set())
        assert routes["GET /v1/company/context"].service_name == "OmniNexu"

    def test_bazaar_extension_present(self):
        routes = register("0xPAY", "eip155:8453", set())
        cfg = routes["GET /v1/company/context"]
        assert "bazaar" in cfg.extensions
