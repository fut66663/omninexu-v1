"""Verify repository data accuracy after seeding."""

import sys

from omninexu.infrastructure.db import SessionLocal
from omninexu.infrastructure.repositories import (
    CompanyRepository,
    FinancialsRepository,
)
from omninexu.observability import get_logger

logger = get_logger(__name__)

# Expected values from official 10-K filings.
EXPECTED_VALUES: dict[tuple[str, int, str], int] = {
    ("AAPL", 2025, "Revenue"): 416_161_000_000,
    ("AAPL", 2025, "NetIncome"): 112_010_000_000,
    ("MSFT", 2025, "Revenue"): 281_724_000_000,
    ("MSFT", 2025, "NetIncome"): 101_832_000_000,
    ("NVDA", 2026, "Revenue"): 215_938_000_000,
    ("NVDA", 2026, "NetIncome"): 120_067_000_000,
}

TOLERANCE = 0.0001  # 0.01%


def verify_ticker(
    ticker: str, company_repo: CompanyRepository, fin_repo: FinancialsRepository
) -> int:
    """Verify a single ticker in the database."""
    ticker_upper = ticker.upper()
    logger.info(f"Verifying repository data for {ticker_upper}")
    failures = 0

    company = company_repo.get_by_ticker(ticker_upper)
    if company is None:
        print(f"{ticker_upper}: company record MISSING -> FAIL")
        return 1

    print(f"{ticker_upper}: company record PASS")

    for concept in ("Revenue", "NetIncome"):
        facts = fin_repo.get_facts(ticker_upper, concept=concept)
        if not facts:
            print(f"  {concept}: MISSING -> FAIL")
            failures += 1
            continue

        fact = facts[0]
        key = (ticker_upper, fact.fiscal_year, concept)
        expected = EXPECTED_VALUES.get(key)
        if expected is None:
            print(
                f"  {concept} FY{fact.fiscal_year}: {int(fact.value)} (no expected value) -> FAIL"
            )
            failures += 1
            continue

        deviation = abs(fact.value - expected) / expected
        status = "PASS" if deviation < TOLERANCE else "FAIL"
        print(
            f"  {concept} FY{fact.fiscal_year}: {int(fact.value)} "
            f"(expected: {expected}, deviation: {deviation:.4%}) -> {status}"
        )
        if deviation >= TOLERANCE:
            failures += 1

    print(f"{ticker_upper}: {failures} FAIL\n")
    return failures


def main(tickers: list[str]) -> int:
    """Run repository verification for the given tickers."""
    db = SessionLocal()
    try:
        company_repo = CompanyRepository(db)
        fin_repo = FinancialsRepository(db)

        total_failures = sum(verify_ticker(ticker, company_repo, fin_repo) for ticker in tickers)
        print(f"TOTAL: {total_failures} FAIL")
        return 1 if total_failures > 0 else 0
    finally:
        db.close()


if __name__ == "__main__":
    tickers = sys.argv[1:] if len(sys.argv) > 1 else ["AAPL", "MSFT", "NVDA"]
    sys.exit(main(tickers))
