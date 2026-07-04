"""Disk-level validation for the OmniNexu data directory.

Provides :class:`DiskValidator` — checks that downloaded files exist,
are non-empty, match expected directory structures, and monitors disk space.
"""

from __future__ import annotations

import shutil
import time
from datetime import UTC, datetime
from pathlib import Path

from omninexu.observability import get_logger

logger = get_logger(__name__)

# ── download space estimation ────────────────────────────────────
_ESTIMATED_BYTES_PER_FILING = 300 * 1024  # 300 KiB per SEC filing
_SPACE_HEADROOM_RATIO = 1.2  # warn below this ratio


class DiskValidator:
    """Validate files and directories on disk.

    All methods are static — the validator holds no mutable state.
    """

    # ── single-file checks ───────────────────────────────────────

    @staticmethod
    def validate_file(path: Path, min_bytes: int = 1) -> bool:
        """Return ``True`` if *path* exists, is a file, and has at least
        *min_bytes* bytes.

        Args:
            path: File to check.
            min_bytes: Minimum expected file size.  Use 0 to accept
                empty (but existing) files.
        """
        try:
            return path.is_file() and path.stat().st_size >= min_bytes
        except OSError:
            return False

    # ── directory-level checks ───────────────────────────────────

    @staticmethod
    def validate_directory(
        base: Path, *, min_files: int = 0, glob: str = "*"
    ) -> tuple[int, int, list[Path]]:
        """Count files under *base* matching *glob*.

        Args:
            base: Directory to scan (recursive).
            min_files: If >0, the actual file count is compared against
                this expected minimum.
            glob: Pattern to match (e.g. ``"*.html"``, ``"*"``).

        Returns:
            ``(found, expected_min, missing_paths)`` where *missing_paths*
            is empty when *min_files* is 0.
        """
        if not base.is_dir():
            logger.warning("Directory not found: %s", base)
            return (0, min_files, [base] if min_files > 0 else [])

        found = [p for p in base.rglob(glob) if p.is_file()]
        count = len(found)
        missing: list[Path] = []

        if min_files > 0 and count < min_files:
            logger.warning(
                "Directory %s has %d files, expected at least %d", base, count, min_files
            )
            missing.append(base)

        return (count, min_files, missing)

    @staticmethod
    def validate_tree(root: Path, structure: dict[str, int]) -> dict[str, int]:
        """Compare actual subdirectory counts against *structure*.

        Args:
            root: Root directory to scan.
            structure: ``{subdir_name: expected_min_files, ...}``.

        Returns:
            ``{subdir_name: actual_count, ...}`` for each key in *structure*.
        """
        actual: dict[str, int] = {}
        for name, expected in structure.items():
            sub = root / name
            count, _, _ = DiskValidator.validate_directory(sub, min_files=expected)
            actual[name] = count
            if count < expected:
                logger.warning(
                    "%s/%s: %d files (expected >= %d)", root.name, name, count, expected
                )
        return actual

    # ── anomaly scans ────────────────────────────────────────────

    @staticmethod
    def find_empty_files(base: Path) -> list[Path]:
        """Return every regular file under *base* whose size is 0 bytes.

        Empty files usually indicate a truncated or failed download.
        """
        if not base.is_dir():
            return []
        return [p for p in base.rglob("*") if p.is_file() and p.stat().st_size == 0]

    @staticmethod
    def find_stale_files(base: Path, max_age_days: int = 30) -> list[Path]:
        """Return files under *base* that haven't been modified in
        *max_age_days* days.
        """
        if not base.is_dir():
            return []
        cutoff = time.time() - (max_age_days * 86400)
        stale: list[Path] = []
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            try:
                if p.stat().st_mtime < cutoff:
                    stale.append(p)
            except OSError:
                continue
        return stale

    @staticmethod
    def find_suspect_directories(base: Path) -> list[Path]:
        """Return directories under *base* whose names don't look like
        valid ticker symbols (1-5 uppercase characters).

        Also flags empty directories and test artifacts (``MagicMock``,
        ``mock``).
        """
        if not base.is_dir():
            return []
        suspect: list[Path] = []
        suspect_names = {"magicmock", "mock", "__pycache__", ".git"}
        for p in base.iterdir():
            if not p.is_dir():
                continue
            name_lower = p.name.lower()
            # Flag known test-artifact names.
            if name_lower in suspect_names:
                suspect.append(p)
                continue
            # Flag empty directories.
            try:
                if not any(p.iterdir()):
                    suspect.append(p)
                    continue
            except OSError:
                continue
            # Flag non-ticker-looking names.
            if not (p.name.upper() == p.name and 1 <= len(p.name) <= 5):
                suspect.append(p)
        return suspect

    # ── disk space ───────────────────────────────────────────────

    @staticmethod
    def check_space(required_bytes: int, path: Path) -> bool:
        """Return ``True`` if the volume containing *path* has at least
        *required_bytes* free.
        """
        try:
            usage = shutil.disk_usage(path)
            return usage.free >= required_bytes
        except OSError:
            return False

    @staticmethod
    def get_directory_size(path: Path) -> int:
        """Recursively sum file sizes under *path*.  Returns 0 for
        non-existent directories.
        """
        if not path.is_dir():
            return 0
        total = 0
        for p in path.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    continue
        return total

    @staticmethod
    def get_growth_trend(base: Path, days: int = 7) -> list[dict[str, object]]:
        """Return per-day size totals for the last *days* days.

        Each entry: ``{"date": "YYYY-MM-DD", "size_bytes": int}``.
        """
        if not base.is_dir():
            return []
        now = time.time()
        cutoff = now - (days * 86400)
        daily: dict[str, int] = {}
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            try:
                mtime = p.stat().st_mtime
            except OSError:
                continue
            if mtime < cutoff:
                continue
            date_str = datetime.fromtimestamp(mtime, tz=UTC).strftime("%Y-%m-%d")
            daily[date_str] = daily.get(date_str, 0) + p.stat().st_size
        return [
            {"date": d, "size_bytes": sz}
            for d, sz in sorted(daily.items())
        ]

    # ── download pre-flight ───────────────────────────────────────

    @staticmethod
    def ensure_download_space(
        n_tickers: int, target_dir: Path, bytes_per_filing: int | None = None
    ) -> None:
        """Check disk space before a batch download; exit if insufficient.

        Logs a WARNING when free space is below the 1.2× headroom ratio.
        Calls ``sys.exit(1)`` when free space is below the 1.0× estimate.

        Args:
            n_tickers: Number of tickers to download.
            target_dir: Target directory (any path on the target volume).
            bytes_per_filing: Estimated bytes per SEC filing (default: 300 KiB).
        """
        import sys

        per_filing = bytes_per_filing if bytes_per_filing is not None else _ESTIMATED_BYTES_PER_FILING
        required = n_tickers * per_filing
        dv = DiskValidator()
        if not dv.check_space(required, target_dir):
            logger.error(
                "Insufficient disk space for %d tickers (need ~%d MiB). Aborting.",
                n_tickers, required // (1024 * 1024),
            )
            sys.exit(1)
        if not dv.check_space(int(required * _SPACE_HEADROOM_RATIO), target_dir):
            logger.warning(
                "Disk space is tight (< %d%% headroom for %d tickers)",
                int((_SPACE_HEADROOM_RATIO - 1) * 100), n_tickers,
            )
