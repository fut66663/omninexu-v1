r"""Post-import validation orchestrator — runs L1/L2/L3 checks for a batch day.

Usage::

    uv run python -m scripts.verify.batch --day 1
    uv run python -m scripts.verify.batch --all
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_scripts_dir = str(Path(__file__).resolve().parent.parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from omninexu.observability import get_logger  # noqa: E402
from verify._common import load_universe  # noqa: E402
from verify.spotcheck import check_l2  # noqa: E402
from verify.statistical import check_l3  # noqa: E402
from verify.structural import check_l1  # noqa: E402

logger = get_logger(__name__)


def verify_day(day: int) -> bool:
    """Run all checks for *day*.  Returns True if all pass."""
    tickers = [c["ticker"] for c in load_universe(day)]
    if not tickers:
        logger.warning(f"Day {day}: no universe data found")
        return False

    logger.info(f"{'=' * 60}")
    logger.info(f"Day {day} Validation — {len(tickers)} companies")
    logger.info(f"{'=' * 60}")

    all_pass = True

    for check_fn, label in [
        (check_l1, "L1 Structural"),
        (check_l2, "L2 Spot-check"),
        (check_l3, "L3 Statistical"),
    ]:
        try:
            result = check_fn(day)
            status = "✅ PASS" if result["pass"] else "❌ FAIL"
            logger.info(f"\n--- {label} {status} ---")
            for k, v in result.items():
                if k in ("level", "pass", "issues"):
                    continue
                logger.info(f"  {k}: {v}")
            if result["issues"]:
                for issue in result["issues"]:
                    logger.warning(f"  ⚠ {issue}")
            if not result["pass"]:
                all_pass = False
        except Exception as exc:
            logger.error(f"  {label} ERROR: {exc}")
            all_pass = False

    logger.info(f"\nDay {day}: {'ALL PASS' if all_pass else 'SOME FAILURES'}")
    return all_pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate batch import results")
    parser.add_argument(
        "--day", type=int, choices=range(1, 6), help="Validate a specific day (1-5)"
    )
    parser.add_argument("--all", action="store_true", help="Validate all 5 days")
    args = parser.parse_args()

    if args.all:
        results = {d: verify_day(d) for d in range(1, 6)}
        passed = sum(1 for v in results.values() if v)
        logger.info(f"\n{'=' * 60}")
        logger.info(f"Overall: {passed}/5 days passed")
        if passed < 5:
            sys.exit(1)
    elif args.day:
        ok = verify_day(args.day)
        if not ok:
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
