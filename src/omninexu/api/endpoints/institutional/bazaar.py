"""Bazaar metadata for Institutional Holdings (Standard, $0.03)."""
from omninexu.api.middleware.x402.helpers import make_bazaar_extension

ENDPOINT_META = {
    "url": "https://api.omninexu.com/v1/company/institutional",
    "description": (
        "SEC 13F institutional holdings for any US-listed stock — "
        "top hedge fund and asset manager positions ranked by market "
        "value. Track whale accumulation, smart money moves, and "
        "fund portfolio changes. "
        "Real SEC EDGAR data, not mock."
    ),
}

_INPUT = {
    "type": "object",
    "properties": {
        "ticker": {"type": "string",
            "description": "US stock ticker (AAPL, BRK.B, TSLA). S&P 500 only.",
            "minLength": 1, "maxLength": 5},
    },
    "required": ["ticker"],
}

_OUTPUT = {
    "ticker": "AAPL",
    "top_holders": [
        {"name": "Vanguard Group", "shares": 1320000000,
         "value": 225000000000, "source_filing_url": "https://..."}
    ],
    "as_of_date": "2026-03-31",
}

BAZAAR_EXTENSION = make_bazaar_extension(
    input_example={"ticker": "AAPL"},
    input_schema=_INPUT, output_example=_OUTPUT,
)
