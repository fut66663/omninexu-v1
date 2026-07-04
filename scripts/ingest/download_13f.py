"""Download 13F institutional holdings and save to DB."""

import argparse

from omninexu.domain.institutional import InstitutionalHolding
from omninexu.infrastructure.clients.edgar_13f import get_13f_holdings
from omninexu.infrastructure.db import SessionLocal
from omninexu.infrastructure.repositories import InstitutionalRepository
from omninexu.observability import get_logger

logger = get_logger(__name__)

DEFAULT_TICKERS = [
    # Core (10) — 6/6 high confidence
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
    # Peer (10) — Phase 1.1 target
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


def download_13f(tickers: list[str] | None = None) -> dict[str, int]:
    tickers = tickers or DEFAULT_TICKERS
    db = SessionLocal()
    repo = InstitutionalRepository(db)
    results: dict[str, int] = {}

    for t in tickers:
        logger.info(f"13F: downloading for {t}")
        try:
            raw = get_13f_holdings(t)
            holdings = [
                InstitutionalHolding(
                    ticker=t,
                    reporting_manager=r["holder_name"],
                    shares=r["shares"],
                    value=r["value"],
                    cusip=r.get("cusip"),
                    report_date=_parse_date(r.get("report_date")),
                    source_filing=r.get("source_filing"),
                )
                for r in raw
            ]
            repo.save_holdings(t, holdings)
            db.commit()
            results[t] = len(holdings)
            logger.info(f"13F: {t} → {len(holdings)} institutions")
        except Exception as exc:
            db.rollback()
            logger.error(f"13F: {t} failed — {exc}")
            results[t] = -1

    db.close()
    return results


def _parse_date(value: str | None):
    if not value:
        return None
    from datetime import date as date_type

    try:
        return date_type.fromisoformat(value)
    except (ValueError, TypeError):
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", nargs="*", default=DEFAULT_TICKERS)
    args = parser.parse_args()

    results = download_13f(args.tickers)
    print(f"\n{'Ticker':<8} {'Institutions':>12}")
    print("-" * 22)
    for t, n in results.items():
        status = "OK" if n > 0 else "FAILED"
        print(f"{t:<8} {n:>12}  {status}")
