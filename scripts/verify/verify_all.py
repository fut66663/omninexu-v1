"""Comprehensive verification of all API-verified companies × 6 dimensions.

L0: Disk coverage (DB companies vs on-disk filing directories)
L1-L3: Existing structural, spot-check, and statistical verification.
"""

from omninexu.application.company_context import CompanyContextService
from omninexu.config import data_paths
from omninexu.infrastructure.db import SessionLocal
from omninexu.infrastructure.storage import CoverageReport

TICKERS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "TSLA",
    "WMT",
    "XOM",
    "JPM",
    "CAT",
    "PFE",
    "GOOGL",
    "ABBV",
    "ABNB",
    "ABT",
    "ACN",
    "ADBE",
    "ADI",
    "ADP",
    "ADSK",
    "AEP",
    "AFL",
]


class FakeCache:
    def get_json(self, key):
        return None

    def set_json(self, key, value, ttl=0):
        pass

    def delete(self, key):
        pass


def main():
    db = SessionLocal()

    # ── L0: Disk coverage ────────────────────────────────────────
    reporter = CoverageReport()
    db_tickers = reporter.get_db_tickers(db)
    comparison = reporter.compare_tickers(data_paths.raw_sec_10k, db_tickers)
    print(
        f"L0 · Disk: {comparison['disk_count']} dirs  "
        f"DB: {comparison['db_count']} tickers  "
        f"Coverage: {comparison['coverage_pct']}%  "
        f"Missing from disk: {len(comparison['db_only'])}"
    )
    if comparison["db_only"]:
        print(f"     Missing from disk: {', '.join(comparison['db_only'][:10])}")
    print()

    service = CompanyContextService(db, cache_backend=FakeCache())
    total_checks = 0
    passed_checks = 0

    for ticker in TICKERS:
        ctx = service.build_context(ticker)
        checks = {
            "fundamentals": len(ctx["fundamentals"]) >= 5,
            "longitudinal": bool(ctx["longitudinal"]),
            "peer_comparison": ctx["peer_comparison"] is not None,
            "institutional": ctx["institutional"] is not None,
            "insider": ctx["insider"] is not None,
            "sources": len(ctx["sources"]) > 0,
        }
        filled = sum(checks.values())
        total_checks += 6
        passed_checks += filled

        dims = " ".join("OK" if v else "--" for v in checks.values())
        print(f"{ticker:<8} [{filled}/6] {dims}  confidence={ctx['confidence']}")

    db.close()
    print(f"\nTOTAL: {passed_checks}/{total_checks} ({100 * passed_checks // total_checks}%)")


if __name__ == "__main__":
    main()
