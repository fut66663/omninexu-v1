"""Bazaar metadata for SEC Filings ($0.002)."""
from omninexu.api.middleware.x402.helpers import make_bazaar_extension

ENDPOINT_META = {
    "url": "https://api.omninexu.com/v1/company/filings",
    "description": (
        "SEC EDGAR filings for any US-listed company — 10-K annual "
        "reports, 10-Q quarterly reports, 8-K material events, and "
        "more. Ticker lookup with direct sec.gov source URLs "
        "and filing dates. All US-listed companies. "
        "Real SEC EDGAR data, not mock."
    ),
}

_INPUT = {
    "type": "object",
    "properties": {
        "ticker": {"type": "string",
            "description": "US stock ticker (AAPL, TSLA, MSFT). Any US-listed company.",
            "minLength": 1, "maxLength": 5},
    },
    "required": ["ticker"],
}

_OUTPUT = {
    "ticker": "AAPL", "company_name": "Apple Inc.",
    "cik": "0000320193",
    "sources": [
        {"type": "10-K", "url": "https://www.sec.gov/Archives/..."},
        {"type": "10-Q", "url": "https://www.sec.gov/Archives/..."},
        {"type": "8-K",  "url": "https://www.sec.gov/Archives/..."},
    ],
    "as_of_date": "2026-03-31",
}

BAZAAR_EXTENSION = make_bazaar_extension(
    input_example={"ticker": "AAPL"},
    input_schema=_INPUT, output_example=_OUTPUT,
)
