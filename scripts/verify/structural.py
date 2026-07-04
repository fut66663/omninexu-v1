"""L1 structural validation — row counts, GICS coverage, fact statistics."""

from __future__ import annotations

import sys
from pathlib import Path

_scripts_dir = str(Path(__file__).resolve().parent.parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from sqlalchemy import func, select  # noqa: E402

from omninexu.infrastructure.db import SessionLocal  # noqa: E402
from omninexu.infrastructure.models import CompanyModel, FinancialFactModel  # noqa: E402
from verify._common import load_universe  # noqa: E402


def check_l1(day: int) -> dict:
    """Verify row counts and coverage for a batch day.

    Returns:
        dict with keys: level, companies_expected, companies_in_db,
        company_coverage_pct, gics_coverage_pct, companies_with_5plus_facts,
        fact_coverage_5plus_pct, companies_with_zero_facts, total_financial_facts,
        pass, issues.
    """
    universe = load_universe(day)
    expected_tickers = {c["ticker"] for c in universe}
    n_expected = len(expected_tickers)

    db = SessionLocal()
    try:
        # Company count
        n_companies = (
            db.scalar(
                select(func.count())
                .select_from(CompanyModel)
                .where(CompanyModel.ticker.in_(expected_tickers))
            )
            or 0
        )

        # GICS coverage
        n_gics = (
            db.scalar(
                select(func.count())
                .select_from(CompanyModel)
                .where(
                    CompanyModel.ticker.in_(expected_tickers),
                    CompanyModel.gics_sector.isnot(None),
                    CompanyModel.gics_sector != "",
                )
            )
            or 0
        )

        # Companies with >= 5 financial facts
        fact_counts = (
            db.execute(
                select(
                    FinancialFactModel.ticker,
                    func.count().label("cnt"),
                )
                .where(FinancialFactModel.ticker.in_(expected_tickers))
                .group_by(FinancialFactModel.ticker)
            )
            .mappings()
            .all()
        )
        n_min5 = sum(1 for r in fact_counts if r["cnt"] >= 5)
        n_zero = len(expected_tickers) - len(fact_counts)

        total_facts = sum(r["cnt"] for r in fact_counts)

    finally:
        db.close()

    result = {
        "level": "L1",
        "companies_expected": n_expected,
        "companies_in_db": n_companies,
        "company_coverage_pct": round(n_companies / n_expected * 100, 1) if n_expected else 0,
        "gics_coverage_pct": round(n_gics / n_expected * 100, 1) if n_expected else 0,
        "companies_with_5plus_facts": n_min5,
        "fact_coverage_5plus_pct": round(n_min5 / n_expected * 100, 1) if n_expected else 0,
        "companies_with_zero_facts": n_zero,
        "total_financial_facts": total_facts,
    }

    # Pass/fail
    issues = []
    if result["company_coverage_pct"] < 100:
        issues.append(f"Missing {n_expected - n_companies} companies in DB")
    if result["gics_coverage_pct"] < 95:
        issues.append(f"GICS coverage {result['gics_coverage_pct']}% < 95%")
    if result["fact_coverage_5plus_pct"] < 90:
        issues.append(f"5+ facts coverage {result['fact_coverage_5plus_pct']}% < 90%")
    result["pass"] = len(issues) == 0
    result["issues"] = issues

    return result
