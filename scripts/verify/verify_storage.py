"""L0 disk storage validation — file counts, empty files, and stale artifacts.

Usage::

    uv run python scripts/verify/verify_storage.py
    uv run python scripts/verify/verify_storage.py --root D:/OmniNexuData
    uv run python scripts/verify/verify_storage.py --checksums
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from omninexu.config import data_paths
from omninexu.infrastructure.storage import ChecksumMan, DiskValidator


def build_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser."""
    p = argparse.ArgumentParser(
        description="L0 disk storage validation for OmniNexu data directories.",
    )
    p.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Data root directory (default: OMNINEXU_DATA_ROOT or D:/OmniNexuData)",
    )
    p.add_argument(
        "--checksums",
        action="store_true",
        help="Also verify manifest-based checksums if a manifest exists under operations/quality/",
    )
    p.add_argument(
        "--stale-days",
        type=int,
        default=30,
        help="Age in days after which a file is considered stale (default: 30)",
    )
    return p


def main() -> int:
    args = build_parser().parse_args()
    root = args.root or data_paths.root
    validator = DiskValidator()
    report: dict = {
        "root": str(root),
        "timestamp": datetime.now(UTC).isoformat(),
        "checks": {},
    }

    # 1. Count raw data directories.
    sec_dir = root / "raw" / "sec"
    report["checks"]["raw_sec_10k"] = {
        "count": len(list((sec_dir / "10-K").iterdir()))
        if (sec_dir / "10-K").is_dir()
        else 0,
        "description": "10-K ticker directories",
    }

    # 2. Find empty files (truncated downloads).
    empties = validator.find_empty_files(sec_dir)
    report["checks"]["empty_files"] = {
        "count": len(empties),
        "paths": [str(p.relative_to(root)) for p in empties[:20]],
        "truncated": len(empties) > 20,
    }

    # 3. Find stale files.
    stales = validator.find_stale_files(sec_dir, max_age_days=args.stale_days)
    report["checks"]["stale_files"] = {
        "count": len(stales),
        "max_age_days": args.stale_days,
        "paths": [str(p.relative_to(root)) for p in stales[:20]],
        "truncated": len(stales) > 20,
    }

    # 4. Optional checksum verification.
    if args.checksums:
        manifest_path = data_paths.quality_dir / "file_manifest.json"
        if manifest_path.exists():
            cm = ChecksumMan()
            passed, failed, _ = cm.verify_manifest(manifest_path)
            report["checks"]["checksums"] = {"passed": passed, "failed": failed}
        else:
            report["checks"]["checksums"] = {
                "skipped": True,
                "reason": f"Manifest not found at {manifest_path}",
            }

    # 5. Summary.
    has_issues = report["checks"]["empty_files"]["count"] > 0
    report["status"] = "issues_found" if has_issues else "ok"

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if has_issues else 0


if __name__ == "__main__":
    sys.exit(main())
