r"""Sync FRED macro-economic data to raw/fred/.

Downloads the five core FRED series and writes each as a CSV
under ``raw/fred/{SERIES_ID}.csv``.  Designed to be called from
the scheduler or standalone.

Usage::

    uv run python scripts/ingest/sync_fred.py
    uv run python scripts/ingest/sync_fred.py --series FEDFUNDS,UNRATE
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from omninexu.config import data_paths
from omninexu.infrastructure.clients.fred_client import CORE_SERIES, FredClient
from omninexu.observability import get_logger

logger = get_logger(__name__)

OUTPUT_DIR = data_paths.raw_fred


def sync_fred(series_ids: list[str] | None = None) -> dict[str, int]:
    """Download FRED series and write CSV files.

    Returns ``{series_id: observation_count}``.
    """
    ids = series_ids or list(CORE_SERIES.keys())
    client = FredClient()

    if not client.is_configured():
        logger.warning("FRED API key not configured — skipping sync")
        return dict.fromkeys(ids, -1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results: dict[str, int] = {}

    for sid in ids:
        try:
            data = client.get_series(sid)
            if not data:
                logger.warning(f"FRED sync: {sid} — no data returned")
                results[sid] = 0
                continue

            csv_path = OUTPUT_DIR / f"{sid}.csv"
            _write_csv(csv_path, data, sid)
            results[sid] = len(data)
            logger.info(f"FRED sync: {sid} — {len(data)} obs → {csv_path}")
        except Exception as exc:
            logger.error(f"FRED sync: {sid} failed — {exc}")
            results[sid] = -1

    return results


def _write_csv(path: Path, data: list[dict], series_id: str) -> None:
    """Write observations to CSV with header: date, value."""
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["date", "value"])
        for obs in data:
            writer.writerow([obs["date"], obs["value"]])


# ── CLI ──────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync FRED macro-economic data"
    )
    parser.add_argument(
        "--series",
        type=str,
        default=None,
        help="Comma-separated series IDs (default: all 5 core)",
    )
    args = parser.parse_args()

    ids = None
    if args.series:
        ids = [s.strip().upper() for s in args.series.split(",") if s.strip()]

    results = sync_fred(ids)
    ok = sum(1 for v in results.values() if v > 0)
    failed = sum(1 for v in results.values() if v == -1)
    logger.info(f"FRED sync done: {ok} ok, {failed} failed")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
