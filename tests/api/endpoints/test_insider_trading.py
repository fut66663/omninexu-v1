"""Tests for insider_trading endpoint registration and metadata."""

from omninexu.api.endpoints.insider_trading import register
from omninexu.api.endpoints.insider_trading.bazaar import BAZAAR_EXTENSION, ENDPOINT_META


class TestRegister:
    def test_returns_route_config(self):
        routes = register("0xPAY", "eip155:8453", set())
        assert routes is not None
        assert len(routes) == 1
        key = list(routes.keys())[0]
        assert key.startswith("GET /v1/company/")

    def test_skips_when_free(self):
        key = list(register("0xPAY", "eip155:8453", set()).keys())[0]
        assert register("0xPAY", "eip155:8453", {key}) is None

    def test_has_bazaar_extension(self):
        routes = register("0xPAY", "eip155:8453", set())
        cfg = list(routes.values())[0]
        assert "bazaar" in cfg.extensions


class TestBazaarMeta:
    def test_url_is_https(self):
        assert ENDPOINT_META["url"].startswith("https://api.omninexu.com")

    def test_description_not_empty(self):
        assert len(ENDPOINT_META["description"]) > 20

    def test_extension_has_method(self):
        assert BAZAAR_EXTENSION["bazaar"]["info"]["input"]["method"] == "GET"

    def test_extension_has_output_example(self):
        out = BAZAAR_EXTENSION["bazaar"]["info"]["output"]["example"]
        assert isinstance(out, dict)
        assert len(out) > 0
