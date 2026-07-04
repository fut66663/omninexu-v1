r"""Batch-seed S&P 500 company records from universe JSON.

Reads the per-day universe JSON produced by ``build_sp500_universe.py``
and creates / updates company rows with full GICS classification.

Usage::

    uv run python scripts/seed_companies_batch.py --day 1
    uv run python scripts/seed_companies_batch.py --day 1 --retry-failed
"""

from __future__ import annotations

import argparse
import json
import sys

from omninexu.config import data_paths
from omninexu.domain.company import Company, IndustryClassification
from omninexu.infrastructure.checkpoint import CheckpointManager
from omninexu.infrastructure.db import SessionLocal
from omninexu.infrastructure.repositories import CompanyRepository
from omninexu.observability import get_logger

logger = get_logger(__name__)


UNIVERSE_DIR = data_paths.processed_universe
CHECKPOINT_DIR = data_paths.checkpoints_dir



def _load_universe(day: int) -> list[dict]:
    path = UNIVERSE_DIR / f"sp500_universe_day{day}.json"
    if not path.exists():
        logger.error(f"Universe file not found: {path}")
        logger.error("Run: uv run python scripts/build_sp500_universe.py first")
        sys.exit(1)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def seed_companies_batch(day: int, retry_failed: bool = False) -> dict[str, int]:
    """Seed all companies for *day* from the universe JSON.

    Returns ``{ticker: 1 (ok) | -1 (failed)}``.
    """
    companies = _load_universe(day)

    # Deduplicate by CIK (GOOG/GOOGL share CIK 0001652044)
    seen_ciks: set[str] = set()
    deduped: list[dict] = []
    for c in companies:
        if c["cik"] in seen_ciks:
            logger.warning(f"  Skipping {c['ticker']}: duplicate CIK {c['cik']}")
            continue
        seen_ciks.add(c["cik"])
        deduped.append(c)
    companies = deduped

    tickers = [c["ticker"] for c in companies]
    phase = "seed_company"

    cpm = CheckpointManager(CHECKPOINT_DIR / f"checkpoint_day{day}.json")

    if retry_failed:
        pending = [e["ticker"] for e in cpm.get_failed(phase)]
        logger.info(f"Day {day}: retrying {len(pending)} failed companies")
    else:
        pending = cpm.get_pending(tickers, phase)

    if not pending:
        logger.info(f"Day {day}: all {len(tickers)} companies already seeded")
        return {}

    logger.info(f"Day {day}: seeding {len(pending)} companies (phase: {phase})")

    db = SessionLocal()
    repo = CompanyRepository(db)
    results: dict[str, int] = {}

    for i, entry in enumerate(companies):
        ticker = entry["ticker"]
        if ticker not in pending:
            continue

        try:
            company = Company(
                ticker=ticker,
                cik=entry["cik"],
                name=entry["name"],
                industry=IndustryClassification(
                    sic_code=entry.get("sic") or None,
                    gics_sector=entry.get("gics_sector") or None,
                    gics_sub_industry=entry.get("gics_sub_industry") or None,
                ),
            )
            repo.create_or_update(company)
            db.commit()
            cpm.mark_completed(ticker, phase)
            results[ticker] = 1

            if (i + 1) % 50 == 0 or (i + 1) == len(companies):
                logger.info(f"  Day {day}: {i + 1}/{len(companies)} seeded")

        except Exception as exc:
            db.rollback()
            logger.error(f"  {ticker}: seed failed — {exc}")
            cpm.mark_failed(ticker, phase, str(exc))
            results[ticker] = -1

    db.close()

    ok = sum(1 for v in results.values() if v == 1)
    failed = sum(1 for v in results.values() if v == -1)
    logger.info(f"Day {day} seed done: {ok} ok, {failed} failed")

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Batch seed S&P 500 companies")
    parser.add_argument("--day", type=int, required=True, choices=range(1, 6),
                        help="Day number (1-5)")
    parser.add_argument("--retry-failed", action="store_true",
                        help="Re-process previously failed tickers")
    args = parser.parse_args()

    results = seed_companies_batch(args.day, retry_failed=args.retry_failed)
    failed = [t for t, v in results.items() if v == -1]
    if failed:
        logger.warning(f"Failed: {', '.join(failed)}")
        logger.info("Re-run with --retry-failed to retry")
        sys.exit(1)


if __name__ == "__main__":
    main()
