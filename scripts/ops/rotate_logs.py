"""Rotate API request logs — delete files older than 90 days.

Usage:
    uv run python scripts/rotate_logs.py
    uv run python scripts/rotate_logs.py --dry-run
"""

import argparse
from datetime import date, timedelta
from pathlib import Path

from omninexu.config import data_paths

RETENTION_DAYS = 90


def rotate(dry_run: bool = False) -> list[Path]:
    """Delete log files older than ``RETENTION_DAYS``.

    Args:
        dry_run: If ``True``, only list files without deleting.

    Returns:
        List of file paths that were (or would be) deleted.
    """
    cutoff = date.today() - timedelta(days=RETENTION_DAYS)
    log_dir = data_paths.logs_api
    deleted: list[Path] = []

    if not log_dir.exists():
        return deleted

    for f in sorted(log_dir.glob("*.jsonl")):
        # File names are ``YYYY-MM.jsonl``.
        try:
            file_date = date.fromisoformat(f.stem + "-01")
        except ValueError:
            continue

        if file_date < cutoff.replace(day=1):
            if not dry_run:
                f.unlink()
            deleted.append(f)

    return deleted


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rotate API request logs")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="List files to delete without actually deleting them",
    )
    args = parser.parse_args()

    removed = rotate(dry_run=args.dry_run)
    if removed:
        action = "Would delete" if args.dry_run else "Deleted"
        for f in removed:
            print(f"{action}: {f}")
        print(f"Total: {len(removed)} file(s)")
    else:
        print("Nothing to rotate.")
