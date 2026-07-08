r"""Batch import SimFin financial facts for S&P 500 companies.

Reads the per-day universe JSON, imports financial facts from the local
SimFin CSV cache, and persists to PostgreSQL with checkpoint support.

Usage::

    uv run python scripts/import_simfin_batch.py --day 1
    uv run python scripts/import_simfin_batch.py --day 1 --retry-failed
"""

from __future__ import annotations

import argparse
import json
import sys

from omninexu.config import data_paths
from omninexu.infrastructure.checkpoint import CheckpointManager
from omninexu.infrastructure.clients.simfin_adapter import SimFinAdapter
from omninexu.infrastructure.db import SessionLocal
from omninexu.infrastructure.repositories import FinancialsRepository
from omninexu.observability import get_logger

logger = get_logger(__name__)


UNIVERSE_DIR = data_paths.processed_universe
CHECKPOINT_DIR = data_paths.checkpoints_dir

# SimFin data cutoff: only import data up to FY2024.
# From FY2025 onwards, SEC EDGAR is the authoritative source.
SIMFIN_CUTOFF_YEAR = 2024


def _load_universe(day: int) -> list[dict]:
    path = UNIVERSE_DIR / f"sp500_universe_day{day}.json"
    if not path.exists():
        logger.error(f"Universe file not found: {path}")
        sys.exit(1)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def import_simfin_batch(day: int, retry_failed: bool = False) -> dict[str, int]:
    """Import SimFin financial facts for all companies in *day*.

    Returns ``{ticker: fact_count (ok) | -1 (failed)}``.
    """
    companies = _load_universe(day)
    tickers = [c["ticker"] for c in companies]
    phase = "simfin"

    cpm = CheckpointManager(CHECKPOINT_DIR / f"checkpoint_day{day}.json")

    if retry_failed:
        pending = [e["ticker"] for e in cpm.get_failed(phase)]
        logger.info(f"Day {day}: retrying {len(pending)} failed companies")
    else:
        pending = cpm.get_pending(tickers, phase)

    if not pending:
        logger.info(f"Day {day}: all {len(tickers)} companies already imported")
        return {}

    logger.info(f"Day {day}: importing SimFin for {len(pending)} companies")

    adapter = SimFinAdapter()
    db = SessionLocal()
    repo = FinancialsRepository(db)
    results: dict[str, int] = {}

    for i, entry in enumerate(companies):
        ticker = entry["ticker"]
        if ticker not in pending:
            continue

        try:
            facts = adapter.get_financial_facts(ticker)
            if facts:
                # SimFin cutoff: only import FY2024 and earlier
                facts = [f for f in facts if f.fiscal_year <= SIMFIN_CUTOFF_YEAR]
            if facts:
                repo.save_facts(facts)
                db.commit()
            results[ticker] = len(facts)
            cpm.mark_completed(ticker, phase, count=len(facts))

            if (i + 1) % 25 == 0 or (i + 1) == len(companies):
                logger.info(f"  Day {day}: {i + 1}/{len(companies)} — {ticker} → {len(facts)} facts")

        except Exception as exc:
            db.rollback()
            logger.error(f"  {ticker}: SimFin import failed — {exc}")
            cpm.mark_failed(ticker, phase, str(exc))
            results[ticker] = -1

    db.close()

    ok = sum(1 for v in results.values() if v >= 0)
    failed = sum(1 for v in results.values() if v == -1)
    total_facts = sum(v for v in results.values() if v > 0)
    logger.info(f"Day {day} SimFin done: {ok} ok, {failed} failed, {total_facts} facts")

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Batch import SimFin financials")
    parser.add_argument("--day", type=int, required=True, choices=range(1, 6),
                        help="Day number (1-5)")
    parser.add_argument("--retry-failed", action="store_true",
                        help="Re-process previously failed tickers")
    args = parser.parse_args()

    results = import_simfin_batch(args.day, retry_failed=args.retry_failed)
    failed = [t for t, v in results.items() if v == -1]
    if failed:
        logger.warning(f"Failed ({len(failed)}): {', '.join(failed[:10])}{'...' if len(failed) > 10 else ''}")
        logger.info("Re-run with --retry-failed to retry")
        sys.exit(1)


if __name__ == "__main__":
    main()
