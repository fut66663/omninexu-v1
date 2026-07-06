"""Discovery metadata — shared across all 8 endpoints.

Search terms change? Edit this file only. Restart applies to all endpoints.

Rules:
- SHARED_TAGS: every endpoint gets these (appear first = highest search weight).
- ENDPOINT_TAGS: endpoint-specific tags — kept within 5-tag total limit.
- SERVICE_NAME: ≤ 32 printable ASCII, used by CDP/agentic.market for categorization.
- ICON_URL: shared service icon.
"""

# ── Service identity ──
SERVICE_NAME = "OmniNexu Financial Data"
ICON_URL = "https://api.omninexu.com/static/icon.png"

# ── Tags shared by ALL endpoints (appear first, draw most search weight) ──
SHARED_TAGS = ["stocks", "finance"]

# ── Endpoint-specific tags (appended after shared). Max 5 total. ──
ENDPOINT_TAGS: dict[str, list[str]] = {
    "company_context":  [
        "fundamentals", "financial-data", "sec-edgar",
    ],
    "filings":          [
        "sec-filings", "edgar", "10-K",
    ],
    "insider_trading":  [
        "insider-trading", "form-4", "sec",
    ],
    "institutional":    [
        "institutional-holdings", "13f", "hedge-funds",
    ],
    "smart_money":      [
        "smart-money", "insider-trading", "13f",
    ],
    "peer_ranking":     [
        "peer-comparison", "industry-ranking", "sp500",
    ],
    "longitudinal":     [
        "cagr", "growth-trends", "longitudinal",
    ],
    "company_pulse":    [
        "signals", "sentiment", "investment-research",
    ],
}


# ── Helper ──
def get_tags(endpoint_key: str) -> list[str]:
    """Return merged [SHARED_TAGS + endpoint_specific], capped at 5."""
    specific = ENDPOINT_TAGS.get(endpoint_key, [])
    merged = SHARED_TAGS + specific
    return merged[:5]
