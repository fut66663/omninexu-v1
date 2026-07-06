"""OmniNexu data warehouse path configuration.

All data paths are defined in one place.  Hard-coding paths elsewhere
in the codebase is forbidden — import from here instead.

Environment
    ``OMNINEXU_DATA_ROOT`` overrides the default root (``D:/OmniNexuData``).
"""

from __future__ import annotations

import os
from pathlib import Path


def _default_root() -> Path:
    return Path(os.getenv("OMNINEXU_DATA_ROOT", "D:/OmniNexuData"))


class DataPaths:
    """Unified data-path manager.

    Usage::

        from omninexu.config import data_paths
        10k_path = data_paths.raw_sec_10k / "AAPL" / "2025-09-27"
        data_paths.ensure_dirs()  # create all Phase-0 directories at startup
    """

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root else _default_root()

    # ── raw · SEC (Phase 0) ────────────────────────────────────

    @property
    def raw_sec(self) -> Path:
        """SEC EDGAR filing originals."""
        return self.root / "raw" / "sec"

    @property
    def raw_sec_10k(self) -> Path:
        """SEC 10-K annual report HTML cache (type-first layout)."""
        return self.raw_sec / "10-K"

    @property
    def raw_simfin(self) -> Path:
        """SimFin bulk CSV dataset."""
        return self.root / "raw" / "simfin"

    # ── raw · SEC (Phase 0, data pending migration) ─────────────

    @property
    def raw_sec_13f(self) -> Path:
        """SEC 13F institutional holdings (Phase 0, data pending migration)."""
        return self.raw_sec / "13F"

    @property
    def raw_sec_form4(self) -> Path:
        """SEC Form 4 insider transactions (Phase 0)."""
        return self.raw_sec / "Form-4"

    # ── raw · SEC (Phase 0–1 reserved) ───────────────────────────

    @property
    def raw_sec_10q(self) -> Path:
        """SEC 10-Q quarterly report HTML cache (Phase 0, not yet downloaded)."""
        return self.raw_sec / "10-Q"

    @property
    def raw_sec_8k(self) -> Path:
        """SEC 8-K current events (Phase 1)."""
        return self.raw_sec / "8-K"

    @property
    def raw_sec_form3(self) -> Path:
        """SEC Form 3 initial insider holdings (Phase 1)."""
        return self.raw_sec / "Form-3"

    @property
    def raw_sec_def14a(self) -> Path:
        """SEC DEF 14A proxy statements (Phase 1)."""
        return self.raw_sec / "DEF-14A"

    @property
    def raw_sec_10ka(self) -> Path:
        """SEC 10-K/A amended annual reports (Phase 1)."""
        return self.raw_sec / "10-KA"

    # ── raw · external sources (Phase 1 planned) ──────────────────

    @property
    def raw_fred(self) -> Path:
        """FRED macro-economic series (Phase 1)."""
        return self.root / "raw" / "fred"

    @property
    def raw_finra(self) -> Path:
        """FINRA TRACE corporate bond data (Phase 1 planned)."""
        return self.root / "raw" / "finra"

    @property
    def raw_cboe(self) -> Path:
        """CBOE historical options EOD data (Phase 1 planned)."""
        return self.root / "raw" / "cboe"

    @property
    def raw_bea(self) -> Path:
        """BEA GDP-by-industry data (Phase 1 planned)."""
        return self.root / "raw" / "bea"

    @property
    def raw_finnhub(self) -> Path:
        """Finnhub options/quotes data (Phase 1 planned)."""
        return self.root / "raw" / "finnhub"

    # ── processed (Phase 0) ────────────────────────────────────

    @property
    def processed_universe(self) -> Path:
        """S&P 500 constituent lists."""
        return self.root / "processed" / "universe"

    @property
    def processed_gics(self) -> Path:
        """SIC → GICS classification mapping."""
        return self.root / "processed" / "gics"

    @property
    def processed_naics(self) -> Path:
        """SIC → NAICS classification mapping (Phase 1)."""
        return self.root / "processed" / "naics"

    # ── processed · reserved (Phase 1–3) ───────────────────────

    @property
    def processed_financials(self) -> Path:
        """XBRL parsing snapshots (parquet)."""
        return self.root / "processed" / "financials"

    @property
    def processed_text(self) -> Path:
        """10-K text extractions (Phase 1)."""
        return self.root / "processed" / "text"

    @property
    def processed_graph(self) -> Path:
        """Knowledge-graph exports (Phase 3)."""
        return self.root / "processed" / "graph"

    # ── products ───────────────────────────────────────────────

    @property
    def products_context(self) -> Path:
        """Company Context API response snapshots."""
        return self.root / "products" / "context"

    @property
    def products_radar(self) -> Path:
        """Supply Chain Radar API response snapshots (Phase 3)."""
        return self.root / "products" / "radar"

    @property
    def products_pulse(self) -> Path:
        """Cross-Asset Pulse API response snapshots (Phase 4)."""
        return self.root / "products" / "pulse"

    # ── operations (Phase 0) ───────────────────────────────────

    @property
    def logs_api(self) -> Path:
        """API request logs (JSONL, 90-day rotation)."""
        return self.root / "operations" / "logs" / "api"

    @property
    def logs_errors(self) -> Path:
        """Structured error/exception logs (JSONL, 90-day rotation)."""
        return self.root / "operations" / "logs" / "errors"

    @property
    def logs_analytics(self) -> Path:
        """Analytics telemetry for the stats dashboard (JSONL, 90-day rotation)."""
        return self.root / "operations" / "logs" / "analytics"

    @property
    def checkpoints_dir(self) -> Path:
        """Batch import checkpoint files (JSONL)."""
        return self.root / "operations" / "checkpoints"

    @property
    def state_dir(self) -> Path:
        """Pipeline state tracking (last-success timestamps)."""
        return self.root / "operations" / "state"

    @property
    def cache_dir(self) -> Path:
        """Redis RDB snapshot directory."""
        return self.root / "operations" / "cache"

    @property
    def backup_dir(self) -> Path:
        """PostgreSQL pg_dump backups (30-day rotation)."""
        return self.root / "operations" / "backups"

    @property
    def quality_dir(self) -> Path:
        """Verification / quality reports."""
        return self.root / "operations" / "quality"

    # ── operations · reserved (Phase 0.5–1) ────────────────────

    @property
    def logs_ingestion(self) -> Path:
        """Data pipeline ingestion logs (JSONL, 90-day rotation, Phase 0.5)."""
        return self.root / "operations" / "logs" / "ingestion"

    @property
    def audit_dir(self) -> Path:
        """Audit snapshots of sold API responses (Phase 0.5)."""
        return self.root / "operations" / "audit"

    @property
    def metrics_dir(self) -> Path:
        """Business metrics (Phase 1)."""
        return self.root / "operations" / "metrics"

    # ── x402 · reserved (Phase 0.5) ────────────────────────────

    @property
    def x402_receipts(self) -> Path:
        """x402 payment receipts (Phase 0.5)."""
        return self.root / "x402" / "receipts"

    @property
    def x402_usage(self) -> Path:
        """x402 usage / billing records (Phase 0.5)."""
        return self.root / "x402" / "usage"

    @property
    def x402_settlements(self) -> Path:
        """x402 USDC settlement records (Phase 0.5)."""
        return self.root / "x402" / "settlements"

    # ── databases ──────────────────────────────────────────────

    @property
    def duckdb_path(self) -> Path:
        """DuckDB analytical database file."""
        return self.root / "db" / "omninexu.duckdb"

    # ── helpers ────────────────────────────────────────────────

    def ensure_dirs(self) -> None:
        """Create all Phase 0 active directories (idempotent).

        Only creates directories for data sources that are actively in use.
        Planned sources (FRED/FINRA/CBOE/BEA/Finnhub) are NOT created here —
        they get their directories when the source is actually connected.
        """
        _dirs = [
            # raw — active Phase 0 sources
            self.raw_sec_10k,
            self.raw_sec_10q,
            self.raw_sec_13f,
            self.raw_sec_form4,
            self.raw_simfin,
            # processed — Phase 0
            self.processed_universe,
            self.processed_gics,
            # products — Phase 0
            self.products_context,
            # operations — Phase 0
            self.logs_api,
            self.logs_errors,
            self.checkpoints_dir,
            self.state_dir,
            self.cache_dir,
            self.backup_dir,
            self.quality_dir,
        ]
        for d in _dirs:
            d.mkdir(parents=True, exist_ok=True)


# Global singleton — import this throughout the codebase.
data_paths = DataPaths()
