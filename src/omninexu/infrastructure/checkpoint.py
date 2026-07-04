"""Checkpoint manager for resumable batch imports.

Stores progress as JSONL (one JSON object per line) so that interrupted
batch scripts can resume without re-processing completed tickers.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class CheckpointManager:
    """JSONL-file-backed progress tracker for batch import phases.

    Each line is a self-contained JSON object.  Appending without
    rewriting the whole file keeps writes cheap and crash-safe: a
    partial final line on crash is simply discarded on next load.

    Usage::

        from omninexu.config import data_paths
        cpm = CheckpointManager(data_paths.checkpoints_dir / "phase_name.json")
        pending = cpm.get_pending(tickers, "simfin")
        for t in pending:
            try:
                do_import(t)
                cpm.mark_completed(t, "simfin", count=45)
            except Exception as exc:
                cpm.mark_failed(t, "simfin", str(exc))
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._entries: dict[tuple[str, str], dict[str, Any]] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def mark_completed(self, ticker: str, phase: str, **meta: Any) -> None:
        """Record a successful completion."""
        self._write(ticker, phase, "ok", **meta)

    def mark_failed(self, ticker: str, phase: str, error: str) -> None:
        """Record a failure (kept so ``--retry-failed`` can target it)."""
        self._write(ticker, phase, "failed", error=error)

    def mark_skip(self, ticker: str, phase: str, reason: str = "") -> None:
        """Record a skipped ticker (e.g. already cached, not needed)."""
        self._write(ticker, phase, "skipped", reason=reason)

    def is_completed(self, ticker: str, phase: str) -> bool:
        """Return True if *ticker* already has a success entry for *phase*."""
        key = (ticker, phase)
        if key in self._entries:
            return self._entries[key].get("status") == "ok"
        return False

    def get_pending(self, tickers: list[str], phase: str) -> list[str]:
        """Return tickers that have NOT been completed for *phase*."""
        return [t for t in tickers if not self.is_completed(t, phase)]

    def get_failed(self, phase: str) -> list[dict[str, Any]]:
        """Return all failed entries for *phase* (for retry)."""
        return [
            e
            for (t, p), e in self._entries.items()
            if p == phase and e.get("status") == "failed"
        ]

    def reset_phase(self, phase: str) -> int:
        """Remove all entries for *phase*.  Returns count of removed entries."""
        before = len(self._entries)
        self._entries = {
            k: v for k, v in self._entries.items() if k[1] != phase
        }
        removed = before - len(self._entries)
        if removed:
            self._flush()
        return removed

    def get_summary(self) -> dict[str, dict[str, int]]:
        """Return per-phase counts: {phase: {'ok': n, 'failed': n, 'pending': n}}."""
        summary: dict[str, dict[str, int]] = {}
        for (_, phase), entry in self._entries.items():
            if phase not in summary:
                summary[phase] = {"ok": 0, "failed": 0, "skipped": 0}
            status = entry.get("status", "unknown")
            if status in ("ok", "failed", "skipped"):
                summary[phase][status] += 1
        return summary

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _write(self, ticker: str, phase: str, status: str, **extra: Any) -> None:
        record: dict[str, Any] = {
            "ticker": ticker,
            "phase": phase,
            "status": status,
            "at": datetime.now(UTC).isoformat(),
            **extra,
        }
        self._entries[(ticker, phase)] = record
        with open(self._path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _load(self) -> None:
        if not self._path.exists():
            return
        seen: set[tuple[str, str]] = set()
        with open(self._path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue  # skip partial/corrupt lines (crash-safe)
                key = (obj["ticker"], obj["phase"])
                # last write wins for a given (ticker, phase)
                if key in seen:
                    del self._entries[key]
                self._entries[key] = obj
                seen.add(key)

    def _flush(self) -> None:
        """Rewrite the file with current in-memory state (used by reset_phase)."""
        with open(self._path, "w", encoding="utf-8") as fh:
            for entry in self._entries.values():
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
