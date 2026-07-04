r"""Build S&P 500 universe JSON files, split into 5 daily batches by sector priority.

Usage::

    uv run python scripts/build_sp500_universe.py [--all] [--day N]

Sources:
    processed/universe/sp500_constituents.csv  (GitHub: fja05680/sp500)

Outputs:
    processed/universe/sp500_day1.json  … day5.json
    processed/universe/sp500_all.json    (--all)

Day assignments (priority order):

    Day 1 — AI, Semiconductors, Cloud, Internet (~100)
        Information Technology + Communication Services + Data Center REITs

    Day 2 — Energy, Industrials, Manufacturing (~101)
        Energy + Industrials

    Day 3 — Financials, Real Estate (~101)
        Financials + remaining Real Estate

    Day 4 — Health Care, Consumer Staples (~100)
        Health Care + Consumer Staples + select Consumer Discretionary

    Day 5 — Consumer Discretionary, Utilities, Materials (~101)
        Remaining Consumer Discretionary + Utilities + Materials
"""

from __future__ import annotations

import csv
import json

# -- Paths -------------------------------------------------------------------
from omninexu.config import data_paths

CSV_PATH = data_paths.processed_universe / "sp500_constituents.csv"
OUT_DIR = data_paths.processed_universe
OUT_DIR.mkdir(parents=True, exist_ok=True)

# -- Data-center REIT tickers (manually curated) ------------------------------
DATA_CENTER_REITS = frozenset({"DLR", "EQIX", "AMT", "CCI", "SBAC", "IRM"})

# -- Day assignments ----------------------------------------------------------

# Day 1: IT + Comms + Data Center REITs
DAY1_SECTORS: dict[str, list[str] | None] = {
    "Information Technology": None,       # all
    "Communication Services": None,       # all
}

# Day 2: Energy + Industrials
DAY2_SECTORS: dict[str, list[str] | None] = {
    "Energy": None,
    "Industrials": None,
}

# Day 3: Financials + Real Estate (excluding data center REITs)
DAY3_SECTORS: dict[str, list[str] | None] = {
    "Financials": None,
    "Real Estate": None,  # data-center REITs already in Day 1
}

# Day 4: Health Care + Consumer Staples
DAY4_SECTORS: dict[str, list[str] | None] = {
    "Health Care": None,
    "Consumer Staples": None,
}

# Day 5: everything else (Consumer Discretionary, Utilities, Materials)
DAY5_SECTORS: dict[str, list[str] | None] = {
    "Consumer Discretionary": None,
    "Utilities": None,
    "Materials": None,
}

# -- Helpers ------------------------------------------------------------------

def _format_cik(raw: str) -> str:
    """Pad CIK to 10 digits with leading zeros (SEC standard format)."""
    return raw.strip().zfill(10)


def _load_companies() -> list[dict[str, str]]:
    """Parse the S&P 500 CSV and return a list of company dicts."""
    companies: list[dict[str, str]] = []
    with open(CSV_PATH, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            companies.append({
                "ticker": row["Symbol"].strip(),
                "name": row["Security"].strip(),
                "cik": _format_cik(row.get("CIK", "")),
                "gics_sector": row.get("GICS Sector", "").strip(),
                "gics_sub_industry": row.get("GICS Sub-Industry", "").strip(),
                "sic": "",  # filled later from SimFin if needed
            })
    return companies


def _assign_day(company: dict[str, str]) -> int:
    """Return the day number (1-5) for a company based on GICS sector."""
    ticker = company["ticker"]
    sector = company["gics_sector"]

    # Day 1 special: data-center REITs go to Day 1
    if ticker in DATA_CENTER_REITS:
        return 1

    if sector in DAY1_SECTORS:
        return 1
    if sector in DAY2_SECTORS:
        return 2
    if sector in DAY3_SECTORS:
        return 3
    if sector in DAY4_SECTORS:
        return 4
    if sector in DAY5_SECTORS:
        return 5

    # Fallback (shouldn't happen with standard GICS sectors)
    print(f"  WARNING: {ticker} ({sector}) not mapped to any day — assigning Day 5")
    return 5


# -- Main ---------------------------------------------------------------------

def main() -> None:
    """Load CSV, assign days, write JSON outputs."""
    print(f"Loading: {CSV_PATH}")
    companies = _load_companies()
    print(f"  {len(companies)} companies loaded\n")

    # Assign days
    buckets: dict[int, list[dict[str, str]]] = {1: [], 2: [], 3: [], 4: [], 5: []}
    for c in companies:
        day = _assign_day(c)
        buckets[day].append(c)

    # Print summary
    print("=== Day Assignments ===\n")
    for day in range(1, 6):
        batch = buckets[day]
        # Sector breakdown per day
        sectors: dict[str, int] = {}
        for c in batch:
            sectors[c["gics_sector"]] = sectors.get(c["gics_sector"], 0) + 1
        sector_str = "  ".join(f"{s}={n}" for s, n in sorted(sectors.items()))
        print(f"  Day {day}: {len(batch)} companies  ({sector_str})")

    # Write per-day JSON
    for day in range(1, 6):
        path = OUT_DIR / f"sp500_universe_day{day}.json"
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(buckets[day], fh, ensure_ascii=False, indent=2)
        print(f"\n  Wrote: {path}")

    # Write combined JSON
    all_path = OUT_DIR / "sp500_universe_all.json"
    with open(all_path, "w", encoding="utf-8") as fh:
        json.dump(companies, fh, ensure_ascii=False, indent=2)
    print(f"\n  Wrote: {all_path} ({len(companies)} total)")

    # Verify total
    grand_total = sum(len(buckets[d]) for d in range(1, 6))
    assert grand_total == len(companies), f"Mismatch: {grand_total} vs {len(companies)}"
    print(f"\nDone. {grand_total} companies assigned across 5 days.")


if __name__ == "__main__":
    main()
