"""Bazaar metadata for Insider Trading (Standard, $0.03)."""
from omninexu.api.middleware.x402.helpers import make_bazaar_extension

ENDPOINT_META = {
    "url": "https://api.omninexu.com/v1/company/insider",
    "description": (
        "SEC Form 4 insider trading for any US-listed stock — "
        "executive buy/sell transactions, cluster detection, "
        "10b5-1 plan filtering, net shares traded, and directional "
        "sentiment signal. Last 90 days. "
        "Real SEC EDGAR data, not mock."
    ),
}

_INPUT = {
    "type": "object",
    "properties": {
        "ticker": {"type": "string",
            "description": "US stock ticker (AAPL, TSLA, NVDA). S&P 500 only.",
            "minLength": 1, "maxLength": 5},
    },
    "required": ["ticker"],
}

_OUTPUT = {
    "ticker": "AAPL",
    "recent_transactions": [
        {"insider_name": "Timothy D. Cook", "insider_title": "CEO",
         "transaction_type": "S", "shares": 10000, "price": 195.0,
         "transaction_date": "2026-06-15"}
    ],
    "net_shares_90d": -5000, "transaction_count_90d": 3,
}

BAZAAR_EXTENSION = make_bazaar_extension(
    input_example={"ticker": "AAPL"},
    input_schema=_INPUT, output_example=_OUTPUT,
)
