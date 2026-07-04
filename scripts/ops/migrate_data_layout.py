r""".. deprecated:: 2026-07-02

This script was written for a one-time disk migration that has been
**completed** as part of the Phase 0–5 data-layout refactor.  The M1–M9
operations it describes are fully executed and the disk is now aligned to
the v2.1 type-first directory structure.

Running this script again is a **no-op** — it will print a message and
exit successfully.  If you need to understand the current layout, see:

- :doc:`omninexu-data-directory-design`
- :doc:`omninexu-storage-architecture-and-status`

The file is kept in the repository for historical reference only.
"""

from __future__ import annotations

import shutil
import sys

from omninexu.config import data_paths
from omninexu.observability import get_logger

logger = get_logger(__name__)

ROOT = data_paths.root
OLD_SEC = ROOT / "raw" / "sec"
NEW_10K = ROOT / "raw" / "sec" / "10-K"
LEGACY = ROOT / "raw" / "sec" / "_legacy"
OLD_PROCESSED = ROOT / "processed"
NEW_UNIVERSE = ROOT / "processed" / "universe"
OLD_OPS = ROOT / "operations"
NEW_CHECKPOINTS = ROOT / "operations" / "checkpoints"
OLD_DB_BACKUP = ROOT / "db" / "backup"
NEW_BACKUPS = ROOT / "operations" / "backups"
OLD_EXPORTS = ROOT / "exports"


def _step(name: str, dry: bool) -> None:
    logger.info(f"{'[DRY-RUN]' if dry else '[EXEC]'} {name}")


# -- M1: 501 {TICKER}/10-K → 10-K/{TICKER} --------------------------

def _migrate_sec_10k(dry: bool) -> int:
    _step("M1: Move {TICKER}/10-K → 10-K/{TICKER}", dry)
    moved = 0
    NEW_10K.mkdir(parents=True, exist_ok=True)
    for d in sorted(OLD_SEC.iterdir()):
        if not d.is_dir() or "_" in d.name or d.name.startswith("10-K"):
            continue
        src = d / "10-K"
        if not src.exists():
            continue
        dst = NEW_10K / d.name
        if dst.exists():
            continue
        if not dry:
            shutil.move(str(src), str(dst))
            # Remove empty ticker dir
            if not any(d.iterdir()):
                d.rmdir()
        moved += 1
    logger.info(f"  {moved} directories moved")
    return moved


# -- M2: 93 {TICKER}_{CIK} → _legacy/ ---------------------------------

def _migrate_legacy_13f(dry: bool) -> int:
    _step("M2: Isolate {TICKER}_{CIK} → _legacy/", dry)
    moved = 0
    LEGACY.mkdir(parents=True, exist_ok=True)
    for d in sorted(OLD_SEC.iterdir()):
        if not d.is_dir() or "_" not in d.name:
            continue
        if d.name.startswith("_legacy"):
            continue
        dst = LEGACY / d.name
        if dst.exists():
            continue
        if not dry:
            shutil.move(str(d), str(dst))
        moved += 1
    logger.info(f"  {moved} directories isolated")
    return moved


# -- M3: Delete debug dirs --------------------------------------------

def _cleanup_debug(dry: bool) -> int:
    _step("M3: Delete debug dirs (CIK1/CIK2)", dry)
    removed = 0
    for d in sorted(OLD_SEC.iterdir()):
        if d.is_dir() and ("CIK1" in d.name or "CIK2" in d.name):
            if not dry:
                shutil.rmtree(d)
            removed += 1
            logger.info(f"  Removed: {d.name}")
    return removed


# -- M4-M6: Move processed files --------------------------------------

def _migrate_processed(dry: bool) -> int:
    _step("M4-M6: Move universe JSONs + constituents CSV", dry)
    moved = 0
    NEW_UNIVERSE.mkdir(parents=True, exist_ok=True)

    # M4: sp500_universe_*.json from processed/ → processed/universe/
    for f in sorted(OLD_PROCESSED.glob("sp500_universe_*.json")):
        dst = NEW_UNIVERSE / f.name
        if dst.exists():
            continue
        if not dry:
            shutil.move(str(f), str(dst))
        moved += 1

    # M5: sp500_constituents.csv from raw/ → processed/universe/
    csv_path = ROOT / "raw" / "sp500_constituents.csv"
    dst = NEW_UNIVERSE / "sp500_constituents.csv"
    if csv_path.exists() and not dst.exists():
        if not dry:
            shutil.move(str(csv_path), str(dst))
        moved += 1

    logger.info(f"  {moved} files moved")
    return moved


# -- M7: Move checkpoints ---------------------------------------------

def _migrate_checkpoints(dry: bool) -> int:
    _step("M7: Move checkpoint JSONs → checkpoints/", dry)
    moved = 0
    NEW_CHECKPOINTS.mkdir(parents=True, exist_ok=True)
    for f in sorted(OLD_OPS.glob("checkpoint_*.json")):
        if f.is_dir():
            continue
        dst = NEW_CHECKPOINTS / f.name
        if dst.exists():
            continue
        if not dry:
            shutil.move(str(f), str(dst))
        moved += 1
    logger.info(f"  {moved} files moved")
    return moved


# -- M8: Move backups -------------------------------------------------

def _migrate_backups(dry: bool) -> int:
    _step("M8: Move db/backup/* → operations/backups/", dry)
    if not OLD_DB_BACKUP.exists():
        logger.info("  0 files (db/backup/ not found or empty)")
        return 0
    moved = 0
    NEW_BACKUPS.mkdir(parents=True, exist_ok=True)
    for f in sorted(OLD_DB_BACKUP.iterdir()):
        dst = NEW_BACKUPS / f.name
        if dst.exists():
            continue
        if not dry:
            shutil.move(str(f), str(dst))
        moved += 1
    # Remove empty db/backup
    if not dry and OLD_DB_BACKUP.exists() and not any(OLD_DB_BACKUP.iterdir()):
        OLD_DB_BACKUP.rmdir()
    logger.info(f"  {moved} files moved")
    return moved


# -- M9: Remove orphan exports/ ---------------------------------------

def _cleanup_exports(dry: bool) -> int:
    _step("M9: Remove orphan exports/", dry)
    if OLD_EXPORTS.exists():
        if not dry:
            shutil.rmtree(OLD_EXPORTS)
        logger.info("  Removed exports/")
        return 1
    logger.info("  0 (exports/ not found)")
    return 0


# -- Main --------------------------------------------------------------

STEPS = [
    ("sec_10k", _migrate_sec_10k),
    ("legacy_13f", _migrate_legacy_13f),
    ("cleanup_debug", _cleanup_debug),
    ("processed", _migrate_processed),
    ("checkpoints", _migrate_checkpoints),
    ("backups", _migrate_backups),
    ("exports", _cleanup_exports),
]


def migrate(dry_run: bool = False) -> dict[str, int]:
    """Execute all migration steps.  Returns {step_name: count_moved}."""
    results: dict[str, int] = {}
    for name, fn in STEPS:
        results[name] = fn(dry_run)
    total = sum(results.values())
    logger.info(f"Migration {'dry-run' if dry_run else 'complete'}: {total} items")
    return results


def main() -> None:
    """Print deprecation notice and exit.

    The migration was completed on 2026-07-02.  This script is retained
    for historical reference only.
    """
    print(
        "migrate_data_layout.py is deprecated.\n"
        "The D:\\OmniNexuData\\ disk layout was migrated to type-first\n"
        "on 2026-07-02 (Phase 0–5 data-layout refactor).\n"
        "See docs/omninexu-data-directory-design.md for the current spec.\n"
        "This script is a no-op and will exit now.",
        file=sys.stderr,
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
