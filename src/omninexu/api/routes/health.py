"""Health check router — infrastructure + pipeline + data status."""

import json
import shutil
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from omninexu.config import data_paths
from omninexu.infrastructure.cache import cache
from omninexu.infrastructure.db import get_db
from omninexu.observability import get_logger

router = APIRouter()
logger = get_logger(__name__)

# ── helpers ──────────────────────────────────────────────────────

def _read_pipeline_states() -> dict[str, dict[str, Any]]:
    """Read all pipeline state files, return {pipeline_name: {last_run, status}}."""
    state_dir = data_paths.state_dir
    pipelines: dict[str, dict[str, Any]] = {}
    if state_dir.is_dir():
        for f in sorted(state_dir.iterdir()):
            if f.suffix == ".json" and f.name.startswith("last_"):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    pipelines[data.get("pipeline", f.stem)] = {
                        "last_run": data.get("last_run"),
                        "status": data.get("status", "unknown"),
                    }
                except (json.JSONDecodeError, KeyError):
                    pass
    return pipelines


def _count_tickers(product_type: str) -> int:
    """Count directories under products/{product_type}/."""
    prod_dir = getattr(data_paths, f"products_{product_type}", None)
    if prod_dir and prod_dir.is_dir():
        return sum(1 for d in prod_dir.iterdir() if d.is_dir())
    return 0


def _count_api_calls_today() -> int:
    """Count API log lines for today (approximate)."""
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    month_str = datetime.now(UTC).strftime("%Y-%m")
    log_path = data_paths.logs_api / f"{month_str}.jsonl"
    if not log_path.exists():
        return 0
    count = 0
    try:
        with open(log_path, encoding="utf-8") as fh:
            for line in fh:
                if today in line:
                    count += 1
    except Exception:
        pass
    return count


# ── endpoint ─────────────────────────────────────────────────────

@router.get("/health")
async def health_check(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Health check — infrastructure, pipeline, and data status."""
    result: dict[str, Any] = {
        "status": "ok",
        "database": "ok",
        "cache": "ok",
        "duckdb": "ok",
    }

    # ── infrastructure checks ──
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning(f"Health DB failure: {exc}")
        result["database"] = "error"
        result["status"] = "degraded"

    try:
        cache.client.ping()
    except Exception as exc:
        logger.warning(f"Health cache failure: {exc}")
        result["cache"] = "error"
        result["status"] = "degraded"

    try:
        import duckdb
        db_path = str(data_paths.duckdb_path)
        if not __import__("os").path.exists(db_path):
            result["duckdb"] = "unavailable"
        else:
            con = duckdb.connect(db_path)
            con.execute("SELECT 1")
            row = con.execute(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema NOT IN ('pg_catalog','information_schema')"
            ).fetchone()
            tables = row[0] if row else 0
            result["duckdb_tables"] = tables
            con.close()
    except Exception as exc:
        logger.warning(f"Health DuckDB failure: {exc}")
        result["duckdb"] = "error"
        result["status"] = "degraded"

    # ── pipeline status ──
    pipelines = _read_pipeline_states()
    if pipelines:
        result["pipelines"] = pipelines
        latest = max(
            (p.get("last_run") or "" for p in pipelines.values()),
            key=lambda x: x,
            default="",
        )
        result["last_pipeline_run"] = latest

    # ── data metrics ──
    result["tickers_in_context"] = _count_tickers("context")
    result["tickers_with_pulse"] = _count_tickers("pulse")

    # ── disk ──
    try:
        usage = shutil.disk_usage(data_paths.root)
        result["disk_free_gb"] = round(usage.free / 1024**3, 1)
    except Exception:
        pass

    # ── API usage today ──
    result["api_calls_today"] = _count_api_calls_today()

    return result
