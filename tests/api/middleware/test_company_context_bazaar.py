"""Tests for company_context Bazaar metadata."""

from omninexu.api.endpoints.company_context.bazaar import (
    BAZAAR_EXTENSION,
    ENDPOINT_META,
)


class TestEndpointMeta:
    def test_url_is_correct(self):
        assert ENDPOINT_META["url"] == (
            "https://api.omninexu.com/v1/company/context"
        )

    def test_description_mentions_sp500(self):
        assert "S&P 500" in ENDPOINT_META["description"]


class TestBazaarExtension:
    def test_output_has_fundamentals(self):
        out = BAZAAR_EXTENSION["bazaar"]["info"]["output"]["example"]
        assert "fundamentals" in out
        assert out["fundamentals"]["Revenue"] == 394328000000

    def test_method_patched(self):
        assert (
            BAZAAR_EXTENSION["bazaar"]["info"]["input"]["method"] == "GET"
        )
