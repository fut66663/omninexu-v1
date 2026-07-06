"""Bazaar metadata for Smart Money Bundle ($0.003)."""
from omninexu.api.middleware.x402.helpers import make_bazaar_extension

ENDPOINT_META = {
    "url": "https://api.omninexu.com/v1/company/smart-money",
    "description": (
        "Smart Money Bundle — SEC Form 4 insider trading + SEC 13F "
        "institutional holdings in one API call for any US stock. "
        "See what executives AND hedge funds are doing: insider "
        "buy/sell signals plus top fund positions. "
        "Real SEC EDGAR data, not mock."
    ),
}

_INPUT = {
    "type": "object",
    "properties": {
        "ticker": {"type": "string",
            "description": "US stock ticker (AAPL, MSFT, NVDA). Any US-listed company.",
            "minLength": 1, "maxLength": 5},
    },
    "required": ["ticker"],
}

_OUTPUT = {
    "ticker": "AAPL",
    "insider": {"recent_transactions": [], "net_shares_90d": -5000},
    "institutional": {"top_holders": [], "as_of_date": "2026-03-31"},
}

BAZAAR_EXTENSION = make_bazaar_extension(
    input_example={"ticker": "AAPL"},
    input_schema=_INPUT, output_example=_OUTPUT,
)
