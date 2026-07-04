"""Structured ingestion-pipeline logging.

Provides :class:`PipelineMonitor` -- records download, parse, and save steps
as JSONL log entries with per-run aggregation and health reporting.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from omninexu.config import data_paths
from omninexu.observability import get_logger

logger = get_logger(__name__)


class PipelineMonitor:
    """Record and query structured ingestion step logs.

    Logs are written to ``operations/logs/ingestion/{YYYY-MM}.jsonl``.
    Each line is a self-contained JSON object.  Per-run aggregation
    is done by scanning lines with a matching ``run_id``.

    Usage::

        pm = PipelineMonitor()
        run_id = pm.start_run()
        pm.record_download(run_id, source="edgar", ticker="AAPL",
                           form="10-K", status="ok", duration_ms=812,
                           bytes_written=51200, checksum="sha256:abc...")
        summary = pm.get_run_summary(run_id)
    """

    def __init__(self, log_dir: Path | None = None) -> None:
        self._log_dir = log_dir or data_paths.logs_ingestion
        self._log_dir.mkdir(parents=True, exist_ok=True)

    # -- run lifecycle --------------------------------------------------

    @staticmethod
    def start_run() -> str:
        """Return a new unique run identifier."""
        return uuid.uuid4().hex[:12]

    # -- step recorders -------------------------------------------------

    def record_download(
        self,
        run_id: str,
        *,
        source: str,
        ticker: str,
        form: str,
        status: str,
        duration_ms: float,
        bytes_written: int = 0,
        checksum: str | None = None,
    ) -> None:
        """Log a download step."""
        self._write(
            run_id,
            step="download",
            source=source,
            ticker=ticker,
            form=form,
            status=status,
            duration_ms=duration_ms,
            bytes_written=bytes_written,
            checksum=checksum,
        )

    def record_parse(
        self,
        run_id: str,
        *,
        source: str,
        ticker: str,
        form: str,
        status: str,
        duration_ms: float,
        facts_extracted: int = 0,
    ) -> None:
        """Log a parse step."""
        self._write(
            run_id,
            step="parse",
            source=source,
            ticker=ticker,
            form=form,
            status=status,
            duration_ms=duration_ms,
            facts_extracted=facts_extracted,
        )

    def record_save(
        self,
        run_id: str,
        *,
        source: str,
        ticker: str,
        status: str,
        duration_ms: float,
        rows_inserted: int = 0,
    ) -> None:
        """Log a database save step."""
        self._write(
            run_id,
            step="save",
            source=source,
            ticker=ticker,
            status=status,
            duration_ms=duration_ms,
            rows_inserted=rows_inserted,
        )

    # -- aggregation ----------------------------------------------------

    def get_run_summary(self, run_id: str) -> dict[str, Any]:
        """Return per-step counts and totals for *run_id*.

        Scans the current month's log file.  Returns an empty summary
        when no entries are found.
        """
        entries = self._read_month()
        run_entries = [e for e in entries if e.get("run_id") == run_id]
        if not run_entries:
            return {"run_id": run_id, "entries": 0}

        steps = {"download": 0, "parse": 0, "save": 0}
        failed = 0
        total_ms = 0.0
        total_facts = 0
        total_bytes = 0
        tickers: set[str] = set()

        for e in run_entries:
            step = e.get("step", "")
            if step in steps:
                steps[step] += 1
            if e.get("status") == "failed":
                failed += 1
            total_ms += e.get("duration_ms", 0)
            total_facts += e.get("facts_extracted", 0) + e.get("rows_inserted", 0)
            total_bytes += e.get("bytes_written", 0)
            tickers.add(e.get("ticker", ""))

        return {
            "run_id": run_id,
            "entries": len(run_entries),
            "tickers": len(tickers),
            "steps": steps,
            "failed": failed,
            "total_duration_ms": round(total_ms, 1),
            "total_facts": total_facts,
            "total_bytes": total_bytes,
        }

    def get_health_report(self, days: int = 7) -> dict[str, Any]:
        """Return success/failure counts for the last *days* days.

        Scans the current month's log file only (cross-month scans
        require reading multiple files -- not implemented yet).
        """
        entries = self._read_month()
        now = datetime.now(UTC)
        cutoff = now.timestamp() - (days * 86400)
        recent = [e for e in entries if _parse_ts(e.get("timestamp", "")) >= cutoff]

        ok = sum(1 for e in recent if e.get("status") == "ok")
        failed = sum(1 for e in recent if e.get("status") == "failed")
        total = len(recent)

        return {
            "period_days": days,
            "total_entries": total,
            "ok": ok,
            "failed": failed,
            "success_rate": round(ok / total * 100, 1) if total else 0.0,
        }

    # -- internal -------------------------------------------------------

    def _log_path(self) -> Path:
        """Return the path for the current month's log file."""
        month = datetime.now(UTC).strftime("%Y-%m")
        return self._log_dir / f"{month}.jsonl"

    def _write(self, run_id: str, **fields: object) -> None:
        """Append one JSON line to the monthly log."""
        record: dict[str, object] = {
            "run_id": run_id,
            "timestamp": datetime.now(UTC).isoformat(),
            **fields,
        }
        line = json.dumps(record, ensure_ascii=False)
        try:
            with self._log_path().open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError as exc:
            logger.warning("Failed to write pipeline log: %s", exc)

    def _read_month(self) -> list[dict[str, Any]]:
        """Return all entries from the current month's log file."""
        path = self._log_path()
        if not path.exists():
            return []
        entries: list[dict[str, Any]] = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        except OSError:
            return []
        return entries


def _parse_ts(ts: str) -> float:
    """Parse an ISO 8601 timestamp to a Unix epoch float.  Returns 0 on failure."""
    try:
        return datetime.fromisoformat(ts).timestamp()
    except (ValueError, TypeError):
        return 0.0
