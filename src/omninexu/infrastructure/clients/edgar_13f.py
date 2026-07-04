"""13F institutional holdings downloader.

Uses edgartools module-level ``get_filings`` (NOT ``Company().get_filings``)
because 13F filings are submitted by institutions, not by the operating company.
"""

from typing import Any

from edgar import Company, set_identity

from omninexu.config.settings import settings
from omninexu.infrastructure.clients.edgar_historical import _cache_filing_html
from omninexu.observability import get_logger

logger = get_logger(__name__)

MAJOR_INSTITUTIONS: list[tuple[str, str]] = [
    ("Vanguard Group",       "0000102909"),
    ("BlackRock",            "0001364742"),
    ("State Street",         "0000093751"),
    ("Fidelity",             "0000315066"),
    ("Geode Capital",        "0001166559"),
    ("Norges Bank",          "0001625236"),
    ("Capital Research",     "0001422848"),
    ("JP Morgan Chase",      "0000019617"),
    ("Goldman Sachs",        "0000886982"),
    ("Morgan Stanley",       "0000895421"),
]


def get_13f_holdings(
    ticker: str, identity: str | None = None
) -> list[dict[str, Any]]:
    """Fetch institutional holdings from SEC EDGAR 13F filings.

    For each major institution, downloads the latest 13F-HR and checks
    whether the ticker appears. Results are sorted by value descending.
    Individual institution failures are warned and skipped.

    Returns:
        List of dicts with keys: holder_name, shares, value, cusip,
        report_date, source_filing.
    """
    t = ticker.upper()
    _identity = identity or settings.edgar_identity
    set_identity(_identity)

    results: list[dict[str, Any]] = []
    for name, cik in MAJOR_INSTITUTIONS:
        try:
            filing = Company(cik).get_filings(form="13F-HR").latest(1)
        except Exception as exc:
            logger.warning(f"13F fetch failed for {name} ({cik}): {exc}")
            continue

        if filing is None:
            logger.info(f"No 13F filing found for {name}")
            continue

        report_date_str = filing.period_of_report or ""
        if report_date_str:
            try:
                from datetime import date as date_type
                rd = date_type.fromisoformat(str(report_date_str))
                _cache_filing_html(t, rd, filing, sub_dir="13F-HR")
            except (ValueError, TypeError):
                pass

        try:
            obj = filing.obj()
        except Exception as exc:
            logger.warning(f"13F parse failed for {name} ({filing.accession_no}): {exc}")
            continue

        holdings = obj.holdings  # already a DataFrame
        if holdings is None or holdings.empty:
            continue

        match = holdings[holdings["Ticker"] == t]
        if match.empty:
            continue

        row = match.iloc[0]
        results.append({
            "holder_name": name,
            "shares": _safe_float(row.get("SharesPrnAmount")),
            "value": _safe_float(row.get("Value")),
            "cusip": str(row.get("Cusip", "")) if row.get("Cusip") else None,
            "report_date": str(filing.period_of_report or ""),
            "source_filing": str(filing.accession_no or ""),
        })

    results.sort(key=lambda r: r["value"] or 0, reverse=True)
    logger.info(f"13F: {t} → {len(results)} institutions")
    return results


def _safe_float(value: Any) -> float | None:
    """Convert a DataFrame value to float, returning None on failure."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
