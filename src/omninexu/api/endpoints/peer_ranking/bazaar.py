"""Bazaar metadata for Peer Ranking (Quick, $0.01)."""
from omninexu.api.middleware.x402.helpers import make_bazaar_extension

ENDPOINT_META = {
    "url": "https://api.omninexu.com/v1/company/peer-ranking",
    "description": (
        "Industry peer comparison and competitive ranking for S&P 500 "
        "stocks — see where a company ranks on revenue and net income "
        "within its GICS sub-industry. Competitive positioning in one "
        "call. Real SEC EDGAR data, not mock."
    ),
}

_INPUT = {
    "type": "object",
    "properties": {
        "ticker": {"type": "string",
            "description": "US stock ticker (AAPL, MSFT, GOOGL). S&P 500 only.",
            "minLength": 1, "maxLength": 5},
    },
    "required": ["ticker"],
}

_OUTPUT = {
    "ticker": "AAPL", "company_name": "Apple Inc.",
    "peer_comparison": {
        "industry": "Technology Hardware, Storage & Peripherals",
        "revenue_rank": 1, "revenue_total_peers": 8,
        "net_income_rank": 1, "net_income_total_peers": 8,
    },
}

BAZAAR_EXTENSION = make_bazaar_extension(
    input_example={"ticker": "AAPL"},
    input_schema=_INPUT, output_example=_OUTPUT,
)
