"""Populate GICS industry classification fields from SIC→GICS mapping.

Usage::

    uv run python scripts/import_gics.py --tickers AAPL MSFT NVDA
"""

import argparse

from omninexu.infrastructure.db import SessionLocal
from omninexu.infrastructure.gics_mapping import load_mapping, lookup
from omninexu.infrastructure.repositories import CompanyRepository
from omninexu.observability import get_logger

logger = get_logger(__name__)

DEFAULT_TICKERS = ["AAPL", "MSFT", "NVDA"]


def import_gics(tickers: list[str] | None = None) -> dict[str, str]:
    """Load GICS mapping and update companies in the database.

    Returns:
        Dict mapping ticker → gics_sub_industry (or "SKIPPED" / "NOT FOUND").
    """
    tickers = tickers or DEFAULT_TICKERS
    load_mapping()  # pre-warm cache
    db = SessionLocal()
    repo = CompanyRepository(db)
    results: dict[str, str] = {}

    for ticker in tickers:
        company = repo.get_by_ticker(ticker)
        if company is None:
            logger.warning(f"{ticker}: company not in DB")
            results[ticker] = "NOT FOUND"
            continue

        sic = company.industry.sic_code
        if sic is None:
            logger.warning(f"{ticker}: no SIC code")
            results[ticker] = "NO SIC"
            continue

        gics = lookup(sic)
        if gics is None:
            logger.warning(f"{ticker}: SIC={sic} not in mapping")
            results[ticker] = "NO MAPPING"
            continue

        repo.update_gics(ticker, gics)
        results[ticker] = gics.gics_sub_industry
        logger.info(f"{ticker}: {sic} → {gics.gics_sub_industry}")

    db.close()
    return results


def _summarize(results: dict[str, str]) -> None:
    print(f"\n{'Ticker':<8} {'GICS Sub-Industry'}")
    print("-" * 50)
    for ticker, sub in results.items():
        print(f"{ticker:<8} {sub}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import GICS industry classifications")
    parser.add_argument("--tickers", nargs="*", default=DEFAULT_TICKERS)
    args = parser.parse_args()

    result = import_gics(args.tickers)
    _summarize(result)
