"""L3 statistical validation — negative values, fiscal year sanity, concept coverage."""

from __future__ import annotations

import sys
from pathlib import Path

_scripts_dir = str(Path(__file__).resolve().parent.parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from sqlalchemy import func, select  # noqa: E402

from omninexu.infrastructure.db import SessionLocal  # noqa: E402
from omninexu.infrastructure.models import FinancialFactModel  # noqa: E402
from verify._common import load_universe  # noqa: E402


def check_l3(day: int) -> dict:
    """Run statistical sanity checks on a batch day's data.

    Returns:
        dict with keys: level, negative_revenue_count, negative_assets_count,
        fiscal_year_range, concept_summary, pass, issues.
    """
    universe = load_universe(day)
    tickers = [c["ticker"] for c in universe]

    db = SessionLocal()
    issues: list[str] = []
    try:
        # Negative revenue
        neg_rev = (
            db.scalar(
                select(func.count())
                .select_from(FinancialFactModel)
                .where(
                    FinancialFactModel.ticker.in_(tickers),
                    FinancialFactModel.concept == "Revenue",
                    FinancialFactModel.value < 0,
                )
            )
            or 0
        )

        if neg_rev > 0:
            issues.append(f"{neg_rev} companies have negative Revenue")

        # Negative total assets
        neg_asset = (
            db.scalar(
                select(func.count())
                .select_from(FinancialFactModel)
                .where(
                    FinancialFactModel.ticker.in_(tickers),
                    FinancialFactModel.concept == "TotalAssets",
                    FinancialFactModel.value < 0,
                )
            )
            or 0
        )

        if neg_asset > 0:
            issues.append(f"{neg_asset} companies have negative TotalAssets")

        # Fiscal year sanity (should be 2020-2025 for SimFin data)
        min_year = db.scalar(
            select(func.min(FinancialFactModel.fiscal_year)).where(
                FinancialFactModel.ticker.in_(tickers),
            )
        )
        max_year = db.scalar(
            select(func.max(FinancialFactModel.fiscal_year)).where(
                FinancialFactModel.ticker.in_(tickers),
            )
        )

        if min_year and min_year < 2015:
            issues.append(f"Oldest fiscal_year is {min_year} (expected >= 2015)")
        if max_year and max_year > 2026:
            issues.append(f"Newest fiscal_year is {max_year} (expected <= 2026)")

        # Concept coverage
        concepts = (
            db.execute(
                select(
                    FinancialFactModel.concept,
                    func.count().label("cnt"),
                )
                .where(FinancialFactModel.ticker.in_(tickers))
                .group_by(FinancialFactModel.concept)
            )
            .mappings()
            .all()
        )
        concept_summary = {r["concept"]: r["cnt"] for r in concepts}

    finally:
        db.close()

    return {
        "level": "L3",
        "negative_revenue_count": neg_rev,
        "negative_assets_count": neg_asset,
        "fiscal_year_range": f"{min_year} – {max_year}",
        "concept_summary": {k: v for k, v in sorted(concept_summary.items()) if k},
        "pass": len(issues) == 0,
        "issues": issues,
    }
