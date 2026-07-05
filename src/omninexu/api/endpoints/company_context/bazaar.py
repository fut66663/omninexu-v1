"""Bazaar metadata for Company Context (Quick, $0.02)."""
from omninexu.api.middleware.x402.helpers import make_bazaar_extension

ENDPOINT_META = {
    "url": "https://api.omninexu.com/v1/company/context",
    "description": (
        "Company financial fundamentals with peer comparison and "
        "cross-source confidence scoring for S&P 500 stocks. "
        "Revenue, net income, EPS, assets, liabilities, cash flow "
        "from SEC EDGAR 10-K/10-Q filings. Includes industry peer "
        "ranking and data-quality confidence score. "
        "Real SEC EDGAR data, not mock."
    ),
}

_INPUT = {
    "type": "object",
    "properties": {
        "ticker": {"type": "string",
            "description": "US stock ticker (AAPL, MSFT, GOOGL). S&P 500 only.",
            "minLength": 1, "maxLength": 5},
        "include_peers": {"type": "boolean",
            "description": "Include peer ranking in GICS industry. Default: true."},
    },
    "required": ["ticker"],
}

_OUTPUT = {
    "ticker": "AAPL", "company_name": "Apple Inc.", "confidence": "high",
    "fundamentals": {"Revenue": 394328000000, "NetIncome": 93736000000,
        "EPSDiluted": 6.11, "GrossProfit": 180683000000,
        "OperatingIncome": 123216000000, "TotalAssets": 364980000000,
        "TotalLiabilities": 308030000000, "StockholdersEquity": 56950000000,
        "OperatingCashFlow": 118254000000},
    "peer_comparison": {"industry": "Technology Hardware",
        "revenue_rank": 1, "net_income_rank": 1},
}

BAZAAR_EXTENSION = make_bazaar_extension(
    input_example={"ticker": "AAPL", "include_peers": True},
    input_schema=_INPUT, output_example=_OUTPUT,
)
