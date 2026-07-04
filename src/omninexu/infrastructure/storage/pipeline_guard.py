"""Cache-integrity guard for data pipeline runs.

Wraps :class:`ChecksumMan` and :class:`DiskValidator` so ingest scripts
can verify cached filings before/after a run without managing manifests
by hand.

Usage in an ingest script::

    guard = PipelineGuard()
    corrupt = guard.check_cache(data_paths.raw_sec_10k)
    if corrupt:
        logger.warning("%d corrupt cache files — will re-download", len(corrupt))
    # ... run the pipeline ...
    guard.update_manifest(data_paths.raw_sec_10k)
"""

from __future__ import annotations

from pathlib import Path

from omninexu.config import data_paths
from omninexu.infrastructure.storage.checksum import ChecksumMan
from omninexu.infrastructure.storage.disk_validator import DiskValidator
from omninexu.observability import get_logger

logger = get_logger(__name__)

_MANIFEST_NAME = "cache_manifest.json"


class PipelineGuard:
    """Pre/post-flight cache integrity checks for data pipelines.

    Does **not** modify any data files — only reads them and writes
    a manifest to ``operations/quality/``.
    """

    def __init__(self) -> None:
        self._cm = ChecksumMan()
        self._dv = DiskValidator()

    # -- pre-flight ---------------------------------------------------------

    def check_cache(self, cache_dir: Path) -> list[Path]:
        """Return cached files that are empty or fail checksum verification.

        Also scans for empty files (truncated downloads) and stale files
        (older than 90 days).

        Args:
            cache_dir: E.g. ``data_paths.raw_sec_10k``.

        Returns:
            Paths that should be re-downloaded.
        """
        bad: list[Path] = []

        # 1. Empty files (truncated downloads).
        empties = self._dv.find_empty_files(cache_dir)
        bad.extend(empties)
        if empties:
            logger.warning("Pre-flight: %d empty cache files", len(empties))

        # 2. Manifest checksum verification.
        manifest_path = data_paths.quality_dir / _MANIFEST_NAME
        if manifest_path.exists():
            passed, failed, failed_paths = self._cm.verify_manifest(manifest_path)
            if failed:
                logger.warning(
                    "Pre-flight: %d/%d files failed checksum", failed, passed + failed
                )
                bad.extend(failed_paths)

        return bad

    # -- post-flight --------------------------------------------------------

    def update_manifest(self, cache_dir: Path) -> Path | None:
        """Generate or update the checksum manifest for *cache_dir*.

        Collects all ``filing.html`` files under *cache_dir* and writes
        a manifest to ``operations/quality/cache_manifest.json``.
        """
        html_files = list(cache_dir.rglob("filing.html"))
        if not html_files:
            logger.warning("No filing.html files found under %s", cache_dir)
            return None

        manifest_path = data_paths.quality_dir / _MANIFEST_NAME
        result = self._cm.store_manifest(html_files, manifest_path)
        logger.info(
            "Manifest updated: %d files → %s",
            len(result.get("files", {})),
            manifest_path,
        )
        return manifest_path
