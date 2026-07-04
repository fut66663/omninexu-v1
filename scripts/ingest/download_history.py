"""Download N years of 10-K financial facts for a list of tickers.

Usage::

    uv run python scripts/download_history.py --tickers AAPL MSFT NVDA --num-filings 5
"""

import argparse

from omninexu.infrastructure.clients import EdgarClient
from omninexu.infrastructure.db import SessionLocal
from omninexu.infrastructure.repositories import FinancialsRepository
from omninexu.jobs.seed import seed_company
from omninexu.observability import get_logger

logger = get_logger(__name__)

# (ticker, cik, name, sic)
DEFAULT_TICKERS = [
    ("AAPL", "0000320193", "Apple Inc.", "3571"),
    ("MSFT", "0000789019", "Microsoft Corp", "7372"),
    ("NVDA", "0001018724", "NVIDIA CORP", "3674"),
]


def download_history(
    tickers: list[tuple[str, str, str, str]] | None = None,
    num_filings: int = 5,
) -> dict[str, int]:
    """Download N latest 10-Ks per ticker and persist to the database.

    Returns:
        Dict mapping ticker → fact count.
    """
    tickers = tickers or DEFAULT_TICKERS
    client = EdgarClient()
    db = SessionLocal()
    repo = FinancialsRepository(db)
    results: dict[str, int] = {}

    for ticker, cik, name, sic in tickers:
        logger.info(f"Downloading {num_filings} 10-Ks for {ticker}")
        try:
            seed_company(db, ticker, cik, name, sic)
            facts = client.get_financial_facts(ticker, num_filings=num_filings)
            repo.save_facts(facts)
            db.commit()
            results[ticker] = len(facts)
            logger.info(f"{ticker}: {len(facts)} facts saved")
        except Exception as exc:
            db.rollback()
            logger.error(f"{ticker}: download failed — {exc}")
            results[ticker] = -1

    db.close()
    return results


def _summarize(results: dict[str, int]) -> None:
    """Print a one-line-per-ticker summary."""
    print(f"\n{'Ticker':<8} {'Facts':>6}  Status")
    print("-" * 30)
    for ticker, count in results.items():
        status = "OK" if count > 0 else "FAILED"
        print(f"{ticker:<8} {count:>6}  {status}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download historical 10-K data")
    parser.add_argument("--tickers", nargs="*", default=["AAPL", "MSFT", "NVDA"])
    parser.add_argument("--num-filings", type=int, default=5)
    args = parser.parse_args()

    # Build (ticker, cik, name, sic) tuples from args
    ticker_map = {t: (t, c, n, s) for t, c, n, s in DEFAULT_TICKERS}
    selected = []
    for t in args.tickers:
        if t in ticker_map:
            selected.append(ticker_map[t])
        else:
            logger.warning(f"Unknown ticker (no CIK pre-configured): {t}")

    result = download_history(selected, num_filings=args.num_filings)
    _summarize(result)
