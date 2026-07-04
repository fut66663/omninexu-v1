"""Safe data-directory cleanup -- dry-run by default, requires explicit flags.

Usage::

    uv run python scripts/ops/cleanup_data.py                    # dry-run only
    uv run python scripts/ops/cleanup_data.py --remove-empty     # delete 0-byte files
    uv run python scripts/ops/cleanup_data.py --remove-stale 60  # delete files >60 days
    uv run python scripts/ops/cleanup_data.py --remove-suspect --confirm

"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from omninexu.config import data_paths
from omninexu.infrastructure.storage import DiskValidator


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Clean up OmniNexu data directories (dry-run by default).",
    )
    p.add_argument("--root", type=Path, default=None,
                   help="Data root (default: OMNINEXU_DATA_ROOT)")
    p.add_argument("--remove-empty", action="store_true",
                   help="Delete 0-byte files under raw/sec/")
    p.add_argument("--remove-stale", type=int, default=None, metavar="DAYS",
                   help="Delete files older than DAYS days under raw/sec/")
    p.add_argument("--remove-suspect", action="store_true",
                   help="Delete directories with non-ticker names (needs --confirm)")
    p.add_argument("--confirm", action="store_true",
                   help="Required for --remove-suspect (safety gate)")
    return p


def main() -> int:
    args = build_parser().parse_args()
    root = args.root or data_paths.root
    sec_dir = root / "raw" / "sec"
    deleted = 0
    dv = DiskValidator()

    # 1. Empty files.
    if args.remove_empty:
        empties = dv.find_empty_files(sec_dir)
        for f in empties:
            print(f"  Removing empty: {f.relative_to(root)}")
            try:
                f.unlink()
                deleted += 1
            except OSError as exc:
                print(f"  FAILED: {exc}")
        print(f"Empty files deleted: {deleted}")

    # 2. Stale files.
    if args.remove_stale is not None:
        days = args.remove_stale
        stales = dv.find_stale_files(sec_dir, max_age_days=days)
        for f in stales:
            print(f"  Removing stale: {f.relative_to(root)}")
            try:
                f.unlink()
                deleted += 1
            except OSError as exc:
                print(f"  FAILED: {exc}")
        print(f"Stale files (> {days} days) deleted: {deleted}")

    # 3. Suspect directories.
    if args.remove_suspect:
        if not args.confirm:
            print("ERROR: --remove-suspect requires --confirm")
            return 1
        suspects = dv.find_suspect_directories(sec_dir)
        for d in suspects:
            print(f"  Removing suspect dir: {d.relative_to(root)}")
            try:
                shutil.rmtree(d)
                deleted += 1
            except OSError as exc:
                print(f"  FAILED: {exc}")
        print(f"Suspect directories deleted: {deleted}")

    if not (args.remove_empty or args.remove_stale or args.remove_suspect):
        # Dry-run: report only.
        empties = len(dv.find_empty_files(sec_dir))
        stales = len(dv.find_stale_files(sec_dir, max_age_days=30))
        suspects = len(dv.find_suspect_directories(sec_dir))
        print(f"Dry-run: {empties} empty files, {stales} stale (>30d), "
              f"{suspects} suspect dirs")
        print("Add --remove-empty / --remove-stale N / --remove-suspect --confirm "
              "to perform cleanup.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
