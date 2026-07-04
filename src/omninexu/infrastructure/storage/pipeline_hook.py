"""Lightweight monitoring hook for ingest scripts.

Wraps :class:`PipelineMonitor` so ingest scripts can record each step
with a single method call — no need to manage run_id or build log entries
by hand.

Usage in an ingest script::

    hook = PipelineHook()
    for ticker in pending:
        facts = client.get_financial_facts(ticker)
        hook.record("download", ticker, ok=True, bytes_written=51200)

    hook.record("download", ticker, ok=False, error=str(exc))
    hook.log_summary()  # print or log the run summary
"""

from __future__ import annotations

import time
from pathlib import Path

from omninexu.infrastructure.storage.pipeline_monitor import PipelineMonitor
from omninexu.observability import get_logger

logger = get_logger(__name__)

_STEP_FIELDS: dict[str, tuple[str, ...]] = {
    "download": ("form", "bytes_written", "checksum"),
    "parse": ("form", "facts_extracted"),
    "save": ("rows_inserted",),
}


class PipelineHook:
    """Record pipeline steps with minimal boilerplate.

    Each ``record()`` call writes one JSONL line via the underlying
    :class:`PipelineMonitor`.
    """

    def __init__(self, log_dir: Path | None = None) -> None:
        self._monitor = PipelineMonitor(log_dir)
        self._run_id = self._monitor.start_run()
        self._t0 = time.monotonic()

    def record(
        self,
        step: str,
        ticker: str,
        *,
        ok: bool = True,
        form: str = "10-K",
        bytes_written: int = 0,
        facts_extracted: int = 0,
        rows_inserted: int = 0,
        error: str = "",
        source: str = "edgar",
    ) -> None:
        """Record a pipeline step.

        Args:
            step: ``"download"``, ``"parse"``, or ``"save"``.
            ticker: Stock ticker.
            ok: ``True`` for success, ``False`` for failure.
            form: SEC form type (default ``"10-K"``).
        """
        status = "ok" if ok else "failed"
        duration_ms = (time.monotonic() - self._t0) * 1000

        if step == "download":
            self._monitor.record_download(
                self._run_id, source=source, ticker=ticker, form=form,
                status=status, duration_ms=duration_ms,
                bytes_written=bytes_written,
            )
        elif step == "parse":
            self._monitor.record_parse(
                self._run_id, source=source, ticker=ticker, form=form,
                status=status, duration_ms=duration_ms,
                facts_extracted=facts_extracted,
            )
        elif step == "save":
            self._monitor.record_save(
                self._run_id, source=source, ticker=ticker,
                status=status, duration_ms=duration_ms,
                rows_inserted=rows_inserted,
            )
        else:
            logger.warning("Unknown step type: %s", step)
            return

        if not ok and error:
            logger.warning("  %s %s: %s", ticker, step, error[:120])

    def log_summary(self) -> None:
        """Print a one-line run summary to the logger."""
        s = self._monitor.get_run_summary(self._run_id)
        logger.info(
            "Pipeline run %s: %d entries, %d tickers, %d failed, "
            "total %d ms, %d facts",
            s.get("run_id", ""),
            s.get("entries", 0),
            s.get("tickers", 0),
            s.get("failed", 0),
            int(s.get("total_duration_ms", 0)),
            s.get("total_facts", 0),
        )
