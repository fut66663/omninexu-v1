"""Import historical financial data from SimFin local CSV cache.

Usage::

    uv run python scripts/import_simfin.py --tickers AAPL MSFT NVDA ...
"""

import argparse

from omninexu.infrastructure.clients.simfin_adapter import SimFinAdapter
from omninexu.infrastructure.db import SessionLocal
from omninexu.infrastructure.repositories import FinancialsRepository
from omninexu.observability import get_logger

logger = get_logger(__name__)

DEFAULT_TICKERS = [
    "AAPL", "MSFT", "NVDA", "TSLA", "WMT",
    "XOM", "JPM", "CAT", "PFE", "GOOGL",
]


def import_simfin(tickers: list[str] | None = None) -> dict[str, int]:
    """Import FY2020+ financial facts from SimFin for each ticker."""
    tickers = tickers or DEFAULT_TICKERS
    adapter = SimFinAdapter()
    db = SessionLocal()
    repo = FinancialsRepository(db)
    results: dict[str, int] = {}

    for t in tickers:
        logger.info(f"SimFin import: {t}")
        try:
            facts = adapter.get_financial_facts(t)
            if facts:
                repo.save_facts(facts)
                db.commit()
            results[t] = len(facts)
            logger.info(f"SimFin: {t} → {len(facts)} facts")
        except Exception as exc:
            db.rollback()
            logger.error(f"SimFin: {t} failed — {exc}")
            results[t] = -1

    db.close()
    return results


def _summarize(results: dict[str, int]) -> None:
    print(f"\n{'Ticker':<8} {'Facts':>6}  Status")
    print("-" * 22)
    for t, n in results.items():
        print(f"{t:<8} {n:>6}  {'OK' if n > 0 else 'FAILED'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import SimFin historical data")
    parser.add_argument("--tickers", nargs="*", default=DEFAULT_TICKERS)
    args = parser.parse_args()
    _summarize(import_simfin(args.tickers))
