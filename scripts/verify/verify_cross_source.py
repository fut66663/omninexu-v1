"""Cross-source data verification — compare SimFin vs EDGAR for all tickers.

Usage::

    uv run python scripts/verify/verify_cross_source.py
    uv run python scripts/verify/verify_cross_source.py --ticker AAPL
    uv run python scripts/verify/verify_cross_source.py --year 2023
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from omninexu.application.cross_source import CrossSourceComparator
from omninexu.infrastructure.db import SessionLocal
from omninexu.infrastructure.models import CompanyModel


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cross-source verification: SimFin vs EDGAR"
    )
    parser.add_argument("--ticker", default=None,
                        help="Single ticker (default: all in DB)")
    parser.add_argument("--year", type=int, default=2024,
                        help="Fiscal year to compare (default: 2024)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        tickers = (
            [args.ticker.upper()]
            if args.ticker
            else list(
                db.execute(
                    select(CompanyModel.ticker).order_by(CompanyModel.ticker)
                ).scalars().all()
            )
        )

        results = CrossSourceComparator.compare_batch(db, tickers, args.year)

    finally:
        db.close()

    total_crit = sum(r.critical for r in results)
    total_warn = sum(r.warning for r in results)
    total_info = sum(r.info for r in results)

    # Print tickers with issues.
    for br in results:
        if br.critical or br.warning:
            issues = [
                f"{d.concept}({d.diff_pct:.1f}%)" for d in br.discrepancies
                if d.diff_pct is not None and d.severity in ("critical", "warning")
            ]
            print(f"{br.ticker}: {', '.join(issues[:5])}")

    print(f"\n{len(tickers)} tickers, {total_crit} critical, "
          f"{total_warn} warning, {total_info} info-only")
    return 1 if total_crit else 0


if __name__ == "__main__":
    sys.exit(main())
