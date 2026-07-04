"""Seed S&P 500 sample companies with financial facts and GICS classification."""

from sqlalchemy.orm import Session

from omninexu.infrastructure.clients import EdgarClient
from omninexu.infrastructure.db import SessionLocal
from omninexu.infrastructure.gics_mapping import load_mapping, lookup
from omninexu.infrastructure.repositories import CompanyRepository
from omninexu.jobs.seed import seed_company, seed_company_financials
from omninexu.observability import get_logger

logger = get_logger(__name__)

SAMPLE_TICKERS = [
    ("AAPL",  "0000320193", "Apple Inc.",        "3571"),
    ("MSFT",  "0000789019", "Microsoft Corp",    "7372"),
    ("NVDA",  "0001018724", "NVIDIA CORP",       "3674"),
    ("TSLA",  "0001564590", "Tesla, Inc.",       "3711"),
    ("WMT",   "0000104169", "Walmart Inc.",      "5331"),
    ("XOM",   "0000034088", "Exxon Mobil Corp.", "2911"),
    ("JPM",   "0000019617", "JPMorgan Chase & Co","6021"),
    ("CAT",   "0000018230", "Caterpillar Inc.",  "3531"),
    ("PFE",   "0000078003", "Pfizer Inc.",       "2834"),
    ("GOOGL", "0001652044", "Alphabet Inc.",     "7370"),
]


def _apply_gics(session: Session, ticker: str, sic: str) -> None:
    """Look up and apply GICS classification for a seeded company."""
    gics = lookup(sic)
    if gics is None:
        logger.warning(f"No GICS mapping for {ticker} SIC={sic}")
        return
    CompanyRepository(session).update_gics(ticker, gics)
    logger.info(f"GICS applied: {ticker} → {gics.gics_sub_industry}")


def seed_snp500(
    db: Session | None = None,
    data_source: EdgarClient | None = None,
) -> None:
    """Seed sample companies, their 10-K facts, and GICS classifications."""
    own_session = db is None
    session = db or SessionLocal()
    client = data_source or EdgarClient()

    load_mapping()  # pre-warm GICS cache

    try:
        for ticker, cik, name, sic in SAMPLE_TICKERS:
            seed_company(session, ticker, cik, name, sic)
            seed_company_financials(session, ticker, data_source=client)
            _apply_gics(session, ticker, sic)
        session.commit()
        logger.info(f"Seeded {len(SAMPLE_TICKERS)} companies")
    except Exception:
        session.rollback()
        raise
    finally:
        if own_session:
            session.close()


if __name__ == "__main__":
    seed_snp500()
