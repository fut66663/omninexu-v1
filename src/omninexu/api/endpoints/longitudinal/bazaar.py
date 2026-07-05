"""Bazaar metadata for Longitudinal CAGR (Pro, $0.05)."""
from omninexu.api.middleware.x402.helpers import make_bazaar_extension

ENDPOINT_META = {
    "url": "https://api.omninexu.com/v1/company/longitudinal",
    "description": (
        "Multi-year CAGR growth trends for S&P 500 stocks — revenue, "
        "net income, EPS, operating income, and cash flow compound "
        "annual growth rates over 3-5 years. See long-term performance "
        "trajectory, not just the latest quarter. "
        "Real SEC EDGAR data, not mock."
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
    "longitudinal": {
        "Revenue_CAGR_3Y": 8.5, "NetIncome_CAGR_3Y": 12.3,
        "EPSDiluted_CAGR_3Y": 15.1, "OperatingIncome_CAGR_3Y": 9.2,
        "OperatingCashFlow_CAGR_3Y": 7.8,
    },
    "as_of_date": "2026-03-31",
}

BAZAAR_EXTENSION = make_bazaar_extension(
    input_example={"ticker": "AAPL"},
    input_schema=_INPUT, output_example=_OUTPUT,
)
