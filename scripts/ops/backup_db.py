"""PostgreSQL database backup via pg_dump.

Usage:
    uv run python scripts/backup_db.py
    uv run python scripts/backup_db.py --keep 30

Output:
    D:/OmniNexuData/operations/backups/omninexu_2026-07-02.dump
"""

import argparse
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

from omninexu.config import data_paths
from omninexu.config.settings import settings


def backup(keep_days: int = 30) -> Path | None:
    """Run ``pg_dump --format=custom`` and return the output file path.

    Args:
        keep_days: Number of days of backups to retain.

    Returns:
        Path to the dump file, or ``None`` on failure.
    """
    backup_dir = data_paths.backup_dir
    backup_dir.mkdir(parents=True, exist_ok=True)

    today = date.today().isoformat()
    output_path = backup_dir / f"omninexu_{today}.dump"

    result = subprocess.run(
        [
            "pg_dump",
            settings.database_url,
            "--format=custom",
            "--file", str(output_path),
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"Backup failed: {result.stderr}", file=sys.stderr)
        return None

    # Remove backups older than keep_days.
    cutoff = date.today() - timedelta(days=keep_days)
    for f in sorted(backup_dir.glob("omninexu_*.dump")):
        try:
            file_date = date.fromisoformat(
                f.stem.replace("omninexu_", "")
            )
        except ValueError:
            continue
        if file_date < cutoff:
            f.unlink()
            print(f"Removed old backup: {f.name}")

    print(f"Backup saved: {output_path}")
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Backup PostgreSQL database"
    )
    parser.add_argument(
        "--keep", type=int, default=30,
        help="Days of backups to retain (default: 30)",
    )
    args = parser.parse_args()
    backup(keep_days=args.keep)
