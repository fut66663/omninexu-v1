"""Pipeline scheduler — cron-friendly entry point for all pipelines.

Usage::

    uv run python scripts/ops/scheduler.py sync_edgar
    uv run python scripts/ops/scheduler.py import_simfin --day 1
    uv run python scripts/ops/scheduler.py product_store --tickers AAPL,MSFT,NVDA
    uv run python scripts/ops/scheduler.py sync_fred
    uv run python scripts/ops/scheduler.py export_duckdb
    uv run python scripts/ops/scheduler.py run-all

Environment:
    ``OMNINEXU_DATA_ROOT`` — data directory (default: D:/OmniNexuData on
    Windows, /data on VPS).  All logs and state files are written under
    ``{root}/operations/``.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from typing import Any

from omninexu.config import data_paths
from omninexu.observability import get_logger

logger = get_logger(__name__)

# ── helpers ────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _write_state(pipeline: str, status: str, extra: dict[str, Any] | None = None) -> None:
    """Upsert pipeline state file under operations/state/."""
    state_dir = data_paths.state_dir
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / f"last_{pipeline}.json"

    record: dict[str, Any] = {
        "pipeline": pipeline,
        "last_run": _now_iso(),
        "status": status,
    }
    if extra:
        record.update(extra)

    state_file.write_text(
        json.dumps(record, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info(f"State written: {state_file.name} → {status}")


def _log_ingestion_event(
    pipeline: str, step: str, status: str, duration_ms: float, **kwargs: Any
) -> None:
    """Append a structured ingestion log line."""
    log_dir = data_paths.logs_ingestion
    log_dir.mkdir(parents=True, exist_ok=True)
    month_str = datetime.now(UTC).strftime("%Y-%m")
    log_path = log_dir / f"{month_str}.jsonl"

    entry = {
        "pipeline": pipeline,
        "timestamp": _now_iso(),
        "step": step,
        "status": status,
        "duration_ms": round(duration_ms, 3),
    }
    entry.update(kwargs)

    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _run_script(script_path: str, extra_args: list[str]) -> tuple[int, float]:
    """Run a Python script via subprocess, return (exit_code, duration_ms)."""
    import subprocess

    t0 = time.perf_counter()
    cmd = [sys.executable, script_path] + extra_args

    logger.info(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
        duration_ms = (time.perf_counter() - t0) * 1000

        if result.stdout:
            for line in result.stdout.strip().splitlines()[-10:]:
                logger.info(f"  stdout: {line}")
        if result.stderr:
            for line in result.stderr.strip().splitlines()[-5:]:
                logger.warning(f"  stderr: {line}")

        return result.returncode, duration_ms
    except subprocess.TimeoutExpired:
        duration_ms = (time.perf_counter() - t0) * 1000
        logger.error(f"Timeout after 7200s: {script_path}")
        return -1, duration_ms
    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000
        logger.error(f"Subprocess error: {exc}")
        return -1, duration_ms


def _run_product_store(
    tickers: list[str], product_type: str = "context"
) -> tuple[int, float]:
    """Generate product snapshots for *product_type* (context or pulse)."""
    t0 = time.perf_counter()
    generated = 0
    failed = 0

    logger.info(
        f"product_store: generating {product_type} for {len(tickers)} tickers"
    )

    from omninexu.infrastructure.db import SessionLocal
    from omninexu.infrastructure.product_store import save_product

    if product_type == "pulse":
        from omninexu.application.pulse import build_pulse

        for ticker in tickers:
            try:
                data = build_pulse(ticker.upper())
                if data:
                    save_product("pulse", ticker.upper(), data)
                    generated += 1
                else:
                    failed += 1
            except Exception as exc:
                logger.error(f"product_store pulse: {ticker} failed — {exc}")
                failed += 1
    else:
        from omninexu.application.company_context import CompanyContextService

        db = SessionLocal()
        try:
            service = CompanyContextService(db)
            for ticker in tickers:
                try:
                    data = service.build_context(ticker.upper(), include_peers=True)
                    if data:
                        save_product("context", ticker.upper(), data)
                        generated += 1
                    else:
                        logger.warning(f"product_store: {ticker} returned no data")
                        failed += 1
                except Exception as exc:
                    logger.error(f"product_store: {ticker} failed — {exc}")
                    failed += 1
        finally:
            db.close()

    duration_ms = (time.perf_counter() - t0) * 1000
    logger.info(f"product_store: {generated} ok, {failed} failed in {duration_ms / 1000:.1f}s")
    return 0 if failed == 0 else 1, duration_ms


# ── main pipeline runners ──────────────────────────────────────────

def run_sync_edgar(
    extra_args: list[str] | None = None, form: str = "10-K"
) -> dict[str, Any]:
    """Run SEC EDGAR sync pipeline."""
    cmd_args = (extra_args or []) + ["--form", form]

    exit_code, duration_ms = _run_script(
        "scripts/ingest/sync_edgar_current.py", cmd_args
    )

    status = "completed" if exit_code == 0 else "partial" if exit_code == 1 else "failed"
    _write_state("sync_edgar_current", status,
                 {"exit_code": exit_code, "duration_ms": round(duration_ms)})
    _log_ingestion_event("sync_edgar_current", "run", status, duration_ms,
                         exit_code=exit_code)

    return {"pipeline": "sync_edgar_current", "status": status, "duration_ms": duration_ms}


def run_import_simfin(day: int = 1, retry_failed: bool = False) -> dict[str, Any]:
    """Run SimFin batch import pipeline."""
    args = ["--day", str(day)]
    if retry_failed:
        args.append("--retry-failed")

    exit_code, duration_ms = _run_script("scripts/ingest/import_simfin_batch.py", args)

    status = "completed" if exit_code == 0 else "failed"
    _write_state("import_simfin_batch", status,
                 {"exit_code": exit_code, "day": day, "duration_ms": round(duration_ms)})
    _log_ingestion_event("import_simfin_batch", "run", status, duration_ms,
                         day=day, exit_code=exit_code)

    return {"pipeline": "import_simfin_batch", "status": status, "duration_ms": duration_ms}


def run_product_store(
    tickers: list[str] | None = None, product_type: str = "context"
) -> dict[str, Any]:
    """Run product generation for listed tickers.

    If no tickers provided, reads from the S&P 500 universe file.
    """
    if tickers is None:
        try:
            universe_path = data_paths.processed_universe / "sp500_universe_all.json"
            if universe_path.exists():
                raw = json.loads(universe_path.read_text(encoding="utf-8"))
                tickers = [c["ticker"] for c in raw]
            else:
                logger.error("No universe file found and no tickers provided")
                return {"pipeline": "product_store", "status": "failed",
                        "error": "no tickers"}
        except Exception as exc:
            logger.error(f"Failed to load universe: {exc}")
            return {"pipeline": "product_store", "status": "failed", "error": str(exc)}

    exit_code, duration_ms = _run_product_store(tickers, product_type)

    status = "completed" if exit_code == 0 else "partial" if exit_code == 1 else "failed"
    _write_state("product_store", status,
                 {"tickers_generated": len(tickers) if exit_code == 0 else 0,
                  "duration_ms": round(duration_ms)})
    _log_ingestion_event("product_store", "run", status, duration_ms,
                         tickers_count=len(tickers))

    return {"pipeline": "product_store", "status": status, "duration_ms": duration_ms}


def run_sync_fred(series_ids: list[str] | None = None) -> dict[str, Any]:
    """Run FRED macro-economic data sync."""
    args = []
    if series_ids:
        args.append(f"--series={','.join(series_ids)}")

    exit_code, duration_ms = _run_script("scripts/ingest/sync_fred.py", args)

    status = "completed" if exit_code == 0 else "failed"
    _write_state("sync_fred", status,
                 {"exit_code": exit_code, "duration_ms": round(duration_ms)})
    _log_ingestion_event("sync_fred", "run", status, duration_ms,
                         series_count=len(series_ids) if series_ids else 5)

    return {"pipeline": "sync_fred", "status": status, "duration_ms": duration_ms}


# ── run-all ────────────────────────────────────────────────────────

def run_all(tickers: list[str] | None = None) -> list[dict[str, Any]]:
    """Run all four pipelines in order: FRED → SEC → SimFin → products."""
    results: list[dict[str, Any]] = []

    logger.info("=" * 60)
    logger.info("OmniNexu Pipeline Scheduler — RUN ALL")
    logger.info("=" * 60)

    # 1. Sync FRED
    logger.info("[1/4] FRED macro sync")
    results.append(run_sync_fred())

    # 2. Sync SEC EDGAR
    logger.info("[2/4] SEC EDGAR sync")
    results.append(run_sync_edgar())

    # 3. Import SimFin
    logger.info("[3/4] SimFin import")
    results.append(run_import_simfin())

    # 4. Generate products
    logger.info("[4/4] Product store")
    results.append(run_product_store(tickers))

    # Summary
    ok = sum(1 for r in results if r.get("status") == "completed")
    logger.info(f"All done: {ok}/{len(results)} pipelines completed")
    for r in results:
        logger.info(f"  {r['pipeline']}: {r['status']} ({r.get('duration_ms', 0) / 1000:.1f}s)")

    return results


# ── CLI ────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="OmniNexu Pipeline Scheduler — cron-friendly pipeline runner",
    )
    sub = parser.add_subparsers(dest="command", help="Pipeline to run")

    # sync_edgar
    p_edgar = sub.add_parser("sync_edgar", help="Sync latest SEC filings")
    p_edgar.add_argument("--dry-run", action="store_true")
    p_edgar.add_argument("--retry-failed", action="store_true")
    p_edgar.add_argument("--form", type=str, default="10-K",
                         choices=["10-K", "10-Q"],
                         help="SEC form type (default: 10-K)")

    # import_simfin
    p_simfin = sub.add_parser("import_simfin", help="Import SimFin financial facts")
    p_simfin.add_argument("--day", type=int, default=1)
    p_simfin.add_argument("--retry-failed", action="store_true")

    # product_store
    p_prod = sub.add_parser("product_store", help="Generate product snapshots")
    p_prod.add_argument("--tickers", type=str, default=None,
                        help="Comma-separated ticker list (default: all from universe)")
    p_prod.add_argument("--product", type=str, default="context",
                        choices=["context", "pulse"],
                        help="Product type to generate (default: context)")

    # sync_fred
    p_fred = sub.add_parser("sync_fred", help="Sync FRED macro-economic data")
    p_fred.add_argument("--series", type=str, default=None,
                        help="Comma-separated series IDs (default: all 5 core)")

    # export_duckdb
    sub.add_parser("export_duckdb", help="Export PG data to DuckDB")

    # run-all
    p_all = sub.add_parser("run-all", help="Run all pipelines in order (FRED→SEC→SimFin→Products)")
    p_all.add_argument("--tickers", type=str, default=None,
                       help="Comma-separated ticker list for product_store step")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "sync_edgar":
            extra = []
            if getattr(args, "dry_run", False):
                extra.append("--dry-run")
            if getattr(args, "retry_failed", False):
                extra.append("--retry-failed")
            form = getattr(args, "form", "10-K")
            result = run_sync_edgar(extra, form)
            sys.exit(0 if result["status"] == "completed" else 1)

        elif args.command == "import_simfin":
            result = run_import_simfin(
                day=args.day,
                retry_failed=getattr(args, "retry_failed", False),
            )
            sys.exit(0 if result["status"] == "completed" else 1)

        elif args.command == "product_store":
            tickers = None
            if args.tickers:
                tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
            product_type = getattr(args, "product", "context")
            result = run_product_store(tickers, product_type)
            sys.exit(0 if result["status"] in ("completed", "partial") else 1)

        elif args.command == "sync_fred":
            ids = None
            if getattr(args, "series", None):
                ids = [s.strip().upper() for s in args.series.split(",") if s.strip()]
            result = run_sync_fred(ids)
            sys.exit(0 if result["status"] == "completed" else 1)

        elif args.command == "export_duckdb":
            exit_code, duration_ms = _run_script(
                "scripts/ops/export_duckdb.py", []
            )
            ok = exit_code == 0
            _write_state("export_duckdb",
                         "completed" if ok else "failed",
                         {"duration_ms": round(duration_ms)})
            _log_ingestion_event("export_duckdb", "run",
                                 "completed" if ok else "failed", duration_ms)
            sys.exit(0 if ok else 1)

        elif args.command == "run-all":
            tickers = None
            if getattr(args, "tickers", None):
                tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
            results = run_all(tickers)
            failed = [r for r in results if r.get("status") not in ("completed", "partial")]
            sys.exit(1 if failed else 0)

    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        sys.exit(130)
    except Exception as exc:
        logger.error(f"Fatal: {exc}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
