"""Bazaar metadata for Insider Trading ($0.002)."""
from omninexu.api.middleware.x402.helpers import make_bazaar_extension

ENDPOINT_META = {
    "url": "https://api.omninexu.com/v1/company/insider",
    "description": (
        "SEC Form 4 insider trading for any US-listed stock — "
        "executive buy/sell transactions with name, title, shares, "
        "price and date. Returns net shares traded and transaction "
        "count over the last 90 days. "
        "Real SEC EDGAR data, not mock."
    ),
}

_INPUT = {
    "type": "object",
    "properties": {
        "ticker": {"type": "string",
            "description": "US stock ticker (AAPL, TSLA, NVDA). Any US-listed company.",
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
