"""Verify financial data accuracy against SEC EDGAR 10-K filings.

Usage::

    uv run python scripts/verify_financials.py AAPL MSFT NVDA          # Level 1: accuracy
    uv run python scripts/verify_financials.py AAPL MSFT NVDA --cross-year  # + Level 2
"""

import sys
from collections import defaultdict
from typing import Any

from omninexu.infrastructure.clients import EdgarClient
from omninexu.observability import get_logger

logger = get_logger(__name__)

# Expected values extracted from official SEC 10-K filings.
# Key format: (ticker, fiscal_year, concept).
EXPECTED_VALUES: dict[tuple[str, int, str], int] = {
    # ── Latest year ──────────────────────────────────────────────────
    ("AAPL", 2025, "Revenue"): 416_161_000_000,
    ("AAPL", 2025, "NetIncome"): 112_010_000_000,
    ("MSFT", 2025, "Revenue"): 281_724_000_000,
    ("MSFT", 2025, "NetIncome"): 101_832_000_000,
    ("NVDA", 2026, "Revenue"): 215_938_000_000,
    ("NVDA", 2026, "NetIncome"): 120_067_000_000,
    # ── Historical years ─────────────────────────────────────────────
    ("AAPL", 2024, "Revenue"): 391_035_000_000,
    ("AAPL", 2024, "NetIncome"): 93_736_000_000,
    ("AAPL", 2023, "Revenue"): 383_285_000_000,
    ("AAPL", 2023, "NetIncome"): 96_995_000_000,
    ("MSFT", 2024, "Revenue"): 245_122_000_000,
    ("MSFT", 2024, "NetIncome"): 88_136_000_000,
    ("MSFT", 2023, "Revenue"): 211_915_000_000,
    ("MSFT", 2023, "NetIncome"): 72_361_000_000,
    ("NVDA", 2025, "Revenue"): 130_497_000_000,
    ("NVDA", 2025, "NetIncome"): 72_880_000_000,
    ("NVDA", 2024, "Revenue"): 60_922_000_000,
    ("NVDA", 2024, "NetIncome"): 29_760_000_000,
}

TOLERANCE = 0.0001  # 0.01%


# ── Level 1: accuracy against expected values ────────────────────────


def _find_fact(facts: list[Any], concept: str) -> Any | None:
    matches = [f for f in facts if f.concept == concept]
    return max(matches, key=lambda f: f.fiscal_year) if matches else None


def _check_fact(fact: Any, expected: int, concept: str) -> tuple[bool, str]:
    if fact is None:
        return False, f"{concept}: MISSING"
    deviation = abs(fact.value - expected) / expected
    status = "PASS" if deviation < TOLERANCE else "FAIL"
    msg = (
        f"{concept} FY{fact.fiscal_year}: {int(fact.value)} "
        f"(expected: {expected}, deviation: {deviation:.4%}) -> {status}"
    )
    return deviation < TOLERANCE, msg


def verify_ticker(ticker: str, client: EdgarClient | None = None) -> dict[str, Any]:
    """Verify Revenue and NetIncome accuracy for a single ticker (Level 1)."""
    client = client or EdgarClient()
    t = ticker.upper()
    logger.info(f"Verifying {t}")

    try:
        facts = client.get_financial_facts(t)
    except Exception as exc:
        logger.error(f"Failed to fetch facts for {t}: {exc}")
        return {"ticker": t, "failures": 2, "messages": [str(exc)]}

    failures = 0
    messages: list[str] = []
    for concept in ("Revenue", "NetIncome"):
        fact = _find_fact(facts, concept)
        if fact is None:
            failures += 1
            messages.append(f"{concept}: MISSING")
            continue
        key = (t, fact.fiscal_year, concept)
        expected = EXPECTED_VALUES.get(key)
        if expected is None:
            messages.append(f"{concept} FY{fact.fiscal_year}: SKIP (no expected value)")
            continue
        passed, msg = _check_fact(fact, expected, concept)
        if not passed:
            failures += 1
        messages.append(msg)

    return {"ticker": t, "failures": failures, "messages": messages}


# ── Level 2: cross-year consistency ──────────────────────────────────


def verify_cross_year(ticker: str, client: EdgarClient | None = None) -> dict[str, Any]:
    """Verify overlapping fiscal years match across adjacent 10-Ks (Level 2).

    Fetches the 2 latest 10-Ks. When the same (fiscal_year, concept) appears
    in both filings (e.g. FY2024 in FY2025 comparison column AND standalone
    FY2024 10-K), the values should match within tolerance.
    """
    client = client or EdgarClient()
    t = ticker.upper()
    logger.info(f"Cross-year verification for {t}")

    try:
        facts = client.get_financial_facts(t, num_filings=2)
    except Exception as exc:
        logger.error(f"Cross-year fetch failed for {t}: {exc}")
        return {"ticker": t, "failures": 0, "messages": [str(exc)]}

    # Group by (fiscal_year, concept), compare unique source filings
    groups: dict[tuple[int, str], dict[str, float]] = defaultdict(dict)
    for f in facts:
        if f.concept in ("Revenue", "NetIncome") and f.value is not None:
            groups[(f.fiscal_year, f.concept)][f.source_filing] = f.value

    failures = 0
    messages: list[str] = []
    for (fy, concept), sources in sorted(groups.items()):
        if len(sources) < 2:
            continue
        vals = list(sources.values())
        v1, v2 = vals[0], vals[1]
        deviation = abs(v1 - v2) / max(abs(v1), abs(v2))
        status = "PASS" if deviation < TOLERANCE else "FAIL"
        if status == "FAIL":
            failures += 1
        messages.append(
            f"Cross-year {concept} FY{fy}: {v1:.0f} vs {v2:.0f} "
            f"(deviation: {deviation:.4%}) -> {status}"
        )

    return {"ticker": t, "failures": failures, "messages": messages}


# ── CLI ──────────────────────────────────────────────────────────────


def main(tickers: list[str], cross_year: bool = False) -> int:
    """Run verification for the given tickers and return exit code."""
    client = EdgarClient()
    total_failures = 0

    for ticker in tickers:
        result = verify_ticker(ticker, client=client)
        for msg in result["messages"]:
            print(f"  {msg}")
        print(f"{result['ticker']}: {result['failures']} FAIL\n")
        total_failures += result["failures"]

        if cross_year:
            result = verify_cross_year(ticker, client=client)
            for msg in result["messages"]:
                print(f"  {msg}")
            if result["messages"]:
                print(f"{result['ticker']} cross-year: {result['failures']} FAIL\n")
            total_failures += result["failures"]

    print(f"TOTAL: {total_failures} FAIL")
    return 1 if total_failures > 0 else 0


if __name__ == "__main__":
    args = sys.argv[1:]
    cross_year = "--cross-year" in args
    tickers = [a for a in args if not a.startswith("--")]
    if not tickers:
        tickers = ["AAPL", "MSFT", "NVDA"]
    sys.exit(main(tickers, cross_year=cross_year))
