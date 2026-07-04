r"""Fill EDGAR 10-K data for companies with zero SimFin facts.

Targets the ~60 S&P 500 companies that SimFin does not cover
(mostly insurers, banks, dual-class stocks, and new index additions).

Usage::

    uv run python scripts/fill_edgar_zero_facts.py
    uv run python scripts/fill_edgar_zero_facts.py --retry-failed
    uv run python scripts/fill_edgar_zero_facts.py --dry-run   # list tickers only
"""

from __future__ import annotations

import argparse
import sys
import time

from sqlalchemy import select

from omninexu.config import data_paths
from omninexu.infrastructure.checkpoint import CheckpointManager
from omninexu.infrastructure.clients import EdgarClient
from omninexu.infrastructure.db import SessionLocal
from omninexu.infrastructure.models import CompanyModel, FinancialFactModel
from omninexu.infrastructure.repositories import FinancialsRepository
from omninexu.infrastructure.storage import DiskValidator, PipelineGuard, PipelineHook
from omninexu.observability import get_logger

logger = get_logger(__name__)

CHECKPOINT_DIR = data_paths.checkpoints_dir

PHASE = "edgar_zero_fill"

# SEC EDGAR fair-use rate: ~10 req/s.  We stay at 5 req/s.
DELAY_SECONDS = 0.25  # 4 req/s with margin
BATCH_LOG_EVERY = 10


def _get_zero_fact_tickers() -> list[tuple[str, str, str]]:
    """Return [(ticker, cik, name), ...] for companies with no facts."""
    db = SessionLocal()
    try:
        sub = select(FinancialFactModel.ticker).distinct().subquery()
        rows = (
            db.execute(
                select(
                    CompanyModel.ticker,
                    CompanyModel.cik,
                    CompanyModel.name,
                )
                .where(CompanyModel.ticker.notin_(select(sub.c.ticker)))
                .order_by(CompanyModel.ticker)
            )
            .mappings()
            .all()
        )
        return [(r["ticker"], r["cik"], r["name"]) for r in rows]
    finally:
        db.close()


def _sanitize_ticker(ticker: str) -> str:
    """edgartools expects '-' not '.' for dual-class tickers (BRK.B → BRK-B)."""
    return ticker.replace(".", "-")


def fill_zero_facts(dry_run: bool = False, retry_failed: bool = False) -> dict[str, int]:
    """Download EDGAR 10-K facts for all zero-fact companies.

    Returns ``{ticker: fact_count (ok) | -1 (failed)}``.
    """
    companies = _get_zero_fact_tickers()
    tickers = [c[0] for c in companies]

    if not tickers:
        logger.info("No zero-fact companies found — everything has data!")
        return {}

    logger.info(f"Found {len(tickers)} companies with zero facts")

    if dry_run:
        for t, cik, name in companies:
            logger.info(f"  {t:8s}  {cik:12s}  {name}")
        return {}

    cpm = CheckpointManager(CHECKPOINT_DIR / "checkpoint_edgar_fill.json")

    if retry_failed:
        pending = [e["ticker"] for e in cpm.get_failed(PHASE)]
        logger.info(f"Retrying {len(pending)} previously failed tickers")
    else:
        pending = cpm.get_pending(tickers, PHASE)

    if not pending:
        logger.info("All companies already processed — nothing to do")
        return {}

    logger.info(f"Processing {len(pending)} companies @ {1/DELAY_SECONDS:.0f} req/s")

    guard = PipelineGuard()
    hook = PipelineHook()
    corrupt = guard.check_cache(data_paths.raw_sec_10k)
    if corrupt:
        logger.warning("Pre-flight: %d corrupt cache files detected", len(corrupt))

    client = EdgarClient()
    db = SessionLocal()
    repo = FinancialsRepository(db)
    results: dict[str, int] = {}
    processed = 0

    for entry in companies:
        ticker, cik, name = entry
        if ticker not in pending:
            continue

        edgar_ticker = _sanitize_ticker(ticker)
        label = f"{ticker}" if edgar_ticker == ticker else f"{ticker}→{edgar_ticker}"

        try:
            time.sleep(DELAY_SECONDS)
            facts = client.get_financial_facts(edgar_ticker, num_filings=1)

            if facts:
                repo.save_facts(facts)
                db.commit()
                results[ticker] = len(facts)
                cpm.mark_completed(ticker, PHASE, count=len(facts), source="edgar")
                logger.info(f"  {label}: {len(facts)} facts (1 filing)")
                hook.record("save", ticker, ok=True, rows_inserted=len(facts))

                # Validate the cached filing is non-empty on disk.
                cache_dir = data_paths.raw_sec_10k / ticker
                _htmls = list(cache_dir.rglob("filing.html")) if cache_dir.is_dir() else []
                _empties = [h for h in _htmls if h.stat().st_size == 0]
                if _empties:
                    logger.warning("  %s: %d empty filing.html in cache", label, len(_empties))
            else:
                results[ticker] = 0
                cpm.mark_completed(ticker, PHASE, count=0, source="edgar")
                logger.warning(f"  {label}: 0 facts returned")
                hook.record("save", ticker, ok=True, rows_inserted=0)

        except Exception as exc:
            db.rollback()
            msg = str(exc)[:120]
            logger.error(f"  {label}: FAILED — {msg}")
            cpm.mark_failed(ticker, PHASE, msg)
            results[ticker] = -1
            hook.record("download", ticker, ok=False, error=msg)

        processed += 1
        if processed % BATCH_LOG_EVERY == 0:
            ok = sum(1 for v in results.values() if v >= 0)
            logger.info(f"  Progress: {processed}/{len(pending)} — {ok} ok, {processed - ok} failed")

    db.close()

    ok = sum(1 for v in results.values() if v >= 0)
    failed = sum(1 for v in results.values() if v == -1)
    total_facts = sum(v for v in results.values() if v > 0)
    logger.info(f"Done: {ok} ok, {failed} failed, {total_facts} new facts")

    guard.update_manifest(data_paths.raw_sec_10k)
    hook.log_summary()

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fill EDGAR data for SimFin zero-fact companies"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="List tickers without downloading")
    parser.add_argument("--retry-failed", action="store_true",
                        help="Re-process previously failed tickers")
    args = parser.parse_args()

    # Pre-flight disk space check.
    if not args.dry_run:
        db = SessionLocal()
        try:
            n = db.query(CompanyModel).count()
        finally:
            db.close()
        DiskValidator.ensure_download_space(n, data_paths.raw_sec_10k)

    results = fill_zero_facts(
        dry_run=args.dry_run,
        retry_failed=args.retry_failed,
    )

    if args.dry_run:
        return

    failed = [t for t, v in results.items() if v == -1]
    if failed:
        logger.warning(f"Failed ({len(failed)}): {', '.join(failed)}")
        logger.info("Re-run with --retry-failed to retry")
        sys.exit(1)


if __name__ == "__main__":
    main()
