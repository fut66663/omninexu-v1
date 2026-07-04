"""Disk vs. database coverage comparison.

Provides :class:`CoverageReport` — checks that every company in the
database has corresponding data files on disk, and vice versa.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from omninexu.infrastructure.models import CompanyModel
from omninexu.observability import get_logger

logger = get_logger(__name__)


def _is_ticker_dir(path: Path) -> bool:
    """Return True if *path* looks like a ticker-symbol directory.

    A ticker directory name is 1–5 uppercase characters.
    """
    return path.is_dir() and path.name.upper() == path.name and 1 <= len(path.name) <= 5


class CoverageReport:
    """Compare on-disk ticker directories against database company records.

    Usage::

        reporter = CoverageReport()
        result = reporter.compare_tickers(
            data_paths.raw_sec_10k,
            set(db_session.execute(select(CompanyModel.ticker)).scalars().all()),
        )
        report = reporter.generate_report(500, result)
    """

    @staticmethod
    def count_tickers(base: Path) -> int:
        """Count subdirectories under *base* that look like ticker symbols.

        A ticker directory is any subdirectory whose name is uppercase
        and 1–5 characters.
        """
        if not base.is_dir():
            return 0
        return sum(1 for p in base.iterdir() if _is_ticker_dir(p))

    @staticmethod
    def get_db_tickers(db: Session) -> set[str]:
        """Return the set of ticker symbols in the companies table."""
        try:
            tickers = db.execute(
                select(CompanyModel.ticker)
            ).scalars().all()
            return {t.upper() for t in tickers}
        except Exception as exc:
            logger.error("Failed to query companies table: %s", exc)
            return set()

    @staticmethod
    def compare_tickers(
        disk_dir: Path, db_tickers: set[str]
    ) -> dict[str, Any]:
        """Compare ticker coverage between disk and database.

        Args:
            disk_dir: Directory containing per-ticker subdirectories.
            db_tickers: Set of ticker symbols from the database.

        Returns:
            ``{disk_count, db_count, disk_only, db_only, common, coverage_pct}``
        """
        disk_tickers: set[str] = set()
        if disk_dir.is_dir():
            for p in disk_dir.iterdir():
                if _is_ticker_dir(p):
                    disk_tickers.add(p.name.upper())

        common = disk_tickers & db_tickers
        coverage_pct = (
            round(len(common) / len(db_tickers) * 100, 1) if db_tickers else 0.0
        )

        return {
            "disk_count": len(disk_tickers),
            "db_count": len(db_tickers),
            "disk_only": sorted(disk_tickers - db_tickers),
            "db_only": sorted(db_tickers - disk_tickers),
            "common": len(common),
            "coverage_pct": coverage_pct,
        }

    @staticmethod
    def generate_report(expected: int, comparison: dict[str, Any]) -> dict[str, Any]:
        """Produce a full coverage report.

        Args:
            expected: The expected ticker count (e.g. 500 for S&P 500).
            comparison: Result from :meth:`compare_tickers`.

        Returns:
            A report dict suitable for JSON serialization.
        """
        missing = comparison.get("db_only", [])
        extra = comparison.get("disk_only", [])
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "expected_total": expected,
            "disk_total": comparison["disk_count"],
            "db_total": comparison["db_count"],
            "coverage_pct": comparison["coverage_pct"],
            "missing_from_disk": missing,
            "missing_count": len(missing),
            "extra_on_disk": extra,
            "extra_count": len(extra),
            "status": "ok" if len(missing) == 0 else "incomplete",
        }
