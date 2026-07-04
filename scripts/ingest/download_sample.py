"""Download sample financial facts for AAPL/MSFT/NVDA and save to fixture."""

import json
from pathlib import Path
from typing import Any

from omninexu.domain.financials import FinancialFact
from omninexu.infrastructure.clients import EdgarClient
from omninexu.observability import get_logger

logger = get_logger(__name__)

DEFAULT_TICKERS = ["AAPL", "MSFT", "NVDA"]


def fact_to_dict(fact: FinancialFact) -> dict[str, Any]:
    """Serialize a FinancialFact to a JSON-friendly dict."""
    return {
        "ticker": fact.ticker,
        "fiscal_year": fact.fiscal_year,
        "fiscal_period": fact.fiscal_period,
        "report_date": fact.report_date.isoformat(),
        "concept": fact.concept,
        "value": fact.value,
        "unit": fact.unit,
        "source_filing": fact.source_filing,
    }


def download_sample(tickers: list[str] | None = None) -> dict[str, list[dict[str, Any]]]:
    """Download latest 10-K facts for the given tickers."""
    client = EdgarClient()
    tickers = tickers or DEFAULT_TICKERS
    result: dict[str, list[dict[str, Any]]] = {}

    for ticker in tickers:
        logger.info(f"Downloading sample facts for {ticker}")
        facts = client.get_financial_facts(ticker)
        result[ticker] = [fact_to_dict(f) for f in facts]
        logger.info(f"Downloaded {len(facts)} facts for {ticker}")

    return result


def save_fixture(data: dict[str, list[dict[str, Any]]], path: Path) -> Path:
    """Save sample facts to a JSON fixture file.

    The caller must provide an explicit *path* — there is no default so that
    the script never accidentally writes outside the intended target.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)

    logger.info(f"Saved sample facts to {path}")
    return path


if __name__ == "__main__":
    import sys
    sample_data = download_sample()
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("sample_facts.json")
    save_fixture(sample_data, path=out)
    for ticker, facts in sample_data.items():
        revenue = next((f for f in facts if f["concept"] == "Revenue"), None)
        if revenue:
            print(f"{ticker} Revenue FY{revenue['fiscal_year']}: {int(revenue['value'])}")
