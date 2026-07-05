"""Tests for x402 Bazaar metadata helpers."""

from omninexu.api.middleware.x402.helpers import (
    make_bazaar_extension,
    make_payment_option,
)


class TestMakePaymentOption:
    def test_creates_exact_scheme_option(self):
        opt = make_payment_option("0xPAY", "eip155:8453", "$0.02")
        assert opt.scheme == "exact"
        assert opt.price == "$0.02"
        assert opt.pay_to == "0xPAY"


class TestMakeBazaarExtension:
    def test_includes_method_field(self):
        ext = make_bazaar_extension(
            input_example={"ticker": "AAPL"},
            input_schema={
                "type": "object",
                "properties": {"ticker": {"type": "string"}},
                "required": ["ticker"],
            },
            output_example={"ticker": "AAPL"},
        )
        assert ext["bazaar"]["info"]["input"]["method"] == "GET"

    def test_preserves_output_example(self):
        ext = make_bazaar_extension(
            input_example={},
            input_schema={"type": "object", "properties": {}},
            output_example={"key": "val"},
        )
        assert ext["bazaar"]["info"]["output"]["example"]["key"] == "val"
