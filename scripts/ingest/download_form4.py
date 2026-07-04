"""Download Form 4 insider trades and save to DB."""

import argparse

from omninexu.domain.insider import InsiderTrade
from omninexu.infrastructure.clients.edgar_form4 import get_insider_trades
from omninexu.infrastructure.db import SessionLocal
from omninexu.infrastructure.repositories import InsiderRepository
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
    # Peer (10) — Phase 1.2 target
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


def download_form4(tickers: list[str] | None = None) -> dict[str, int]:
    tickers = tickers or DEFAULT_TICKERS
    db = SessionLocal()
    repo = InsiderRepository(db)
    results: dict[str, int] = {}

    for t in tickers:
        logger.info(f"Form 4: downloading for {t}")
        try:
            raw = get_insider_trades(t, limit=20)
            trades = [
                InsiderTrade(
                    ticker=t,
                    insider_name=r["insider_name"],
                    insider_title=r.get("insider_title"),
                    transaction_type=r["transaction_type"],
                    shares=r.get("shares"),
                    price=r.get("price"),
                    transaction_date=_parse_date(r.get("transaction_date")),
                    source_filing=r.get("source_filing"),
                )
                for r in raw
                if r.get("transaction_date")  # skip rows missing date
            ]
            repo.save_trades(t, trades)
            db.commit()
            results[t] = len(trades)
            logger.info(f"Form 4: {t} → {len(trades)} trades")
        except Exception as exc:
            db.rollback()
            logger.error(f"Form 4: {t} failed — {exc}")
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

    results = download_form4(args.tickers)
    print(f"\n{'Ticker':<8} {'Trades':>8}")
    print("-" * 18)
    for t, n in results.items():
        status = "OK" if n > 0 else "FAILED"
        print(f"{t:<8} {n:>8}  {status}")
