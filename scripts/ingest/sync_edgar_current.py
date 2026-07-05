r"""Sync SEC EDGAR 10-K data as authoritative source for all S&P 500 companies.

Downloads the latest 10-K filing from SEC EDGAR for every company in the
database and upserts financial facts.  EDGAR is the authoritative source;
SimFin data remains as historical reference for fiscal years not covered
by the latest EDGAR filing.

Usage::

    uv run python scripts/sync_edgar_current.py             # full sync
    uv run python scripts/sync_edgar_current.py --dry-run   # estimate only
    uv run python scripts/sync_edgar_current.py --retry-failed
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
from omninexu.infrastructure.models import CompanyModel
from omninexu.infrastructure.repositories import FinancialsRepository
from omninexu.infrastructure.storage import DiskValidator, PipelineGuard, PipelineHook
from omninexu.observability import get_logger

logger = get_logger(__name__)


CHECKPOINT_DIR = data_paths.checkpoints_dir

PHASE = "edgar_current"  # default, overridden by --form
SUPPORTED_FORMS = ("10-K", "10-Q")

DELAY_SECONDS = 0.25  # 4 req/s — well under SEC 10 req/s limit
BATCH_LOG_EVERY = 20

# Dual-class tickers that edgartools cannot resolve by their S&P 500 ticker.
# Map: DB ticker → EDGAR-compatible ticker (same CIK, same financials).
TICKER_ALIASES: dict[str, str] = {
    "BRK.B": "BRK-A",
    "BF.B": "BF-A",
}


def _get_all_tickers() -> list[tuple[str, str, str]]:
    """Return [(ticker, cik, name), ...] for all companies in DB."""
    db = SessionLocal()
    try:
        rows = (
            db.execute(
                select(
                    CompanyModel.ticker,
                    CompanyModel.cik,
                    CompanyModel.name,
                ).order_by(CompanyModel.ticker)
            )
            .mappings()
            .all()
        )
        return [(r["ticker"], r["cik"], r["name"]) for r in rows]
    finally:
        db.close()


def sync_edgar_current(
    dry_run: bool = False,
    retry_failed: bool = False,
    form: str = "10-K",
    ticker_filter: list[str] | None = None,
) -> dict[str, int]:
    """Download latest SEC filing (10-K or 10-Q) for all companies.

    Args:
        ticker_filter: If provided, only sync these tickers.
    """
    form_phase = f"edgar_{form.replace('-', '').lower()}"
    companies = _get_all_tickers()
    if ticker_filter:
        ticker_set = {t.upper() for t in ticker_filter}
        companies = [c for c in companies if c[0] in ticker_set]
    tickers = [c[0] for c in companies]
    n_total = len(tickers)

    if dry_run:
        est_seconds = n_total * DELAY_SECONDS + n_total * 8
        logger.info(f"Dry run ({form}): {n_total} companies")
        logger.info(f"  Estimated time: {est_seconds / 60:.0f} min (~{est_seconds / 3600:.1f} hrs)")
        logger.info(f"  Rate: {1 / DELAY_SECONDS:.0f} req/s")
        return {}

    cp_name = f"checkpoint_edgar_{form.replace('-', '').lower()}.json"
    cpm = CheckpointManager(CHECKPOINT_DIR / cp_name)

    if retry_failed:
        pending = [e["ticker"] for e in cpm.get_failed(form_phase)]
        logger.info(f"Retrying {len(pending)} previously failed tickers")
    else:
        pending = cpm.get_pending(tickers, form_phase)

    if not pending:
        logger.info(f"All {n_total} companies already synced")
        return {}

    logger.info(f"Syncing {len(pending)}/{n_total} companies ({form}) from SEC EDGAR")
    logger.info(f"  Rate: {1 / DELAY_SECONDS:.0f} req/s, ETA: ~{len(pending) * (DELAY_SECONDS + 8) / 60:.0f} min")

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

        edgar_ticker = TICKER_ALIASES.get(ticker, ticker)
        label = f"{ticker}" if edgar_ticker == ticker else f"{ticker}←{edgar_ticker}"

        try:
            time.sleep(DELAY_SECONDS)
            facts = client.get_financial_facts(edgar_ticker, num_filings=1, form=form)
            hook.record("download", ticker, ok=True,
                        bytes_written=sum(f.stat().st_size for f in
                            (data_paths.raw_sec_10k / ticker).rglob("filing.html"))
                            if (data_paths.raw_sec_10k / ticker).is_dir() else 0)

            if facts:
                # Rewrite ticker if using alias (BRK-A → BRK.B)
                if edgar_ticker != ticker:
                    for f in facts:
                        f.ticker = ticker

                repo.save_facts(facts)  # upsert — EDGAR overwrites same keys
                db.commit()
                results[ticker] = len(facts)
                cpm.mark_completed(ticker, form_phase, count=len(facts), source="edgar")
                hook.record("save", ticker, ok=True, rows_inserted=len(facts))

                # Validate the cached filing is non-empty on disk.
                cache_dir = data_paths.raw_sec_10k / ticker
                _htmls = list(cache_dir.rglob("filing.html")) if cache_dir.is_dir() else []
                _empties = [h for h in _htmls if h.stat().st_size == 0]
                if _empties:
                    logger.warning("  %s: %d empty filing.html in cache", label, len(_empties))
            else:
                results[ticker] = 0
                cpm.mark_completed(ticker, form_phase, count=0, source="edgar")
                hook.record("save", ticker, ok=True, rows_inserted=0)
                logger.warning(f"  {label}: 0 facts parsed")

        except Exception as exc:
            db.rollback()
            msg = str(exc)[:120]
            logger.error(f"  {label}: FAILED — {msg}")
            cpm.mark_failed(ticker, form_phase, msg)
            results[ticker] = -1
            hook.record("download", ticker, ok=False, error=msg)

        processed += 1
        if processed % BATCH_LOG_EVERY == 0:
            ok = sum(1 for v in results.values() if v >= 0)
            elapsed = processed * (DELAY_SECONDS + 8)  # rough
            remaining = (len(pending) - processed) * (DELAY_SECONDS + 8)
            logger.info(
                f"  [{processed}/{len(pending)}] {ok} ok, {processed - ok} failed"
                f" — elapsed ~{elapsed / 60:.0f}m, remaining ~{remaining / 60:.0f}m"
            )

    db.close()

    ok = sum(1 for v in results.values() if v >= 0)
    failed = sum(1 for v in results.values() if v == -1)
    total_facts = sum(v for v in results.values() if v > 0)
    logger.info(f"Done: {ok} ok, {failed} failed, {total_facts} new/updated facts from SEC EDGAR")

    guard.update_manifest(data_paths.raw_sec_10k)
    hook.log_summary()

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync latest SEC EDGAR 10-K data for all S&P 500 companies"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Show estimate without downloading")
    parser.add_argument("--retry-failed", action="store_true",
                        help="Re-process previously failed tickers")
    parser.add_argument("--form", type=str, default="10-K",
                        choices=["10-K", "10-Q"],
                        help="SEC form type (default: 10-K)")
    parser.add_argument("--tickers", type=str, default=None,
                        help="Comma-separated tickers to sync (default: all)")
    args = parser.parse_args()

    # Pre-flight disk space check.
    if not args.dry_run:
        db = SessionLocal()
        try:
            n = db.query(CompanyModel).count()
        finally:
            db.close()
        DiskValidator.ensure_download_space(n, data_paths.raw_sec_10k)

    ticker_filter = None
    if args.tickers:
        ticker_filter = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]

    results = sync_edgar_current(
        dry_run=args.dry_run,
        retry_failed=args.retry_failed,
        form=args.form,
        ticker_filter=ticker_filter,
    )

    if args.dry_run:
        return

    failed = [t for t, v in results.items() if v == -1]
    if failed:
        logger.warning(f"Failed ({len(failed)}): {', '.join(failed[:10])}{'...' if len(failed) > 10 else ''}")
        logger.info("Re-run with --retry-failed to retry")
        sys.exit(1)


if __name__ == "__main__":
    main()
