"""L2 spot-check validation — known revenue values for anchor companies."""

from __future__ import annotations

import sys
from pathlib import Path

_scripts_dir = str(Path(__file__).resolve().parent.parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from sqlalchemy import select  # noqa: E402

from omninexu.infrastructure.db import SessionLocal  # noqa: E402
from omninexu.infrastructure.models import FinancialFactModel  # noqa: E402
from verify._common import ANCHOR_REVENUE, load_universe  # noqa: E402


def check_l2(day: int) -> dict:
    """Spot-check known revenue values for anchor companies.

    Returns:
        dict with keys: level, checked, discrepancies, pass, issues.
    """
    universe = load_universe(day)
    universe_tickers = {c["ticker"] for c in universe}

    # Filter anchors that are in this day's batch
    anchors = {t: v for t, v in ANCHOR_REVENUE.items() if t in universe_tickers}
    if not anchors:
        return {
            "level": "L2",
            "checked": 0,
            "pass": True,
            "issues": [],
            "note": "no anchors in this batch",
        }

    db = SessionLocal()
    discrepancies: list[str] = []
    checked = 0
    try:
        for ticker, expected_rev in anchors.items():
            fact = (
                db.execute(
                    select(FinancialFactModel)
                    .where(
                        FinancialFactModel.ticker == ticker,
                        FinancialFactModel.concept == "Revenue",
                    )
                    .order_by(FinancialFactModel.fiscal_year.desc())
                    .limit(1)
                )
                .scalars()
                .first()
            )

            if fact is None:
                discrepancies.append(f"{ticker}: no Revenue fact found")
                continue

            actual = fact.value
            if actual is None:
                discrepancies.append(f"{ticker}: Revenue value is NULL")
                continue

            # Revenue is stored in actual dollars, anchor values are in millions
            actual_m = actual / 1_000_000
            pct_diff = abs(actual_m - expected_rev) / expected_rev * 100

            if pct_diff > 5.0:
                discrepancies.append(
                    f"{ticker}: Revenue={actual_m:.0f}M vs expected {expected_rev:.0f}M ({pct_diff:.1f}% diff)"
                )
            checked += 1

    finally:
        db.close()

    return {
        "level": "L2",
        "checked": checked,
        "discrepancies": discrepancies,
        "pass": len(discrepancies) == 0,
        "issues": discrepancies,
    }
