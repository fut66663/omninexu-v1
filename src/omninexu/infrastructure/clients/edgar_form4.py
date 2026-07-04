"""Form 4 insider transactions downloader."""

from typing import Any

from edgar import Company, set_identity

from omninexu.config.settings import settings
from omninexu.infrastructure.clients.edgar_historical import _cache_filing_html
from omninexu.observability import get_logger

logger = get_logger(__name__)


def get_insider_trades(
    ticker: str, limit: int = 20, identity: str | None = None
) -> list[dict[str, Any]]:
    """Fetch Form 4 insider transactions via edgartools ``to_dataframe()``.

    Only returns P (purchase) and S (sale) codes.
    Form 4/A amendments deduplicated by accession number.
    """
    t = ticker.upper()
    _identity = identity or settings.edgar_identity
    set_identity(_identity)

    company = Company(t)
    filings = company.get_filings(form="4").latest(limit)

    results: list[dict[str, Any]] = []
    seen: set[str] = set()

    for filing in filings:
        accession = filing.accession_no or ""
        if accession in seen:
            continue
        seen.add(accession)

        try:
            obj = filing.obj()
            _cache_filing_html(t, filing.filing_date, filing, sub_dir="Form-4")
            df = obj.to_dataframe()
        except Exception as exc:
            logger.warning(f"Form 4 parse failed {accession}: {exc}")
            continue

        if df is None or df.empty:
            continue

        for _, row in df.iterrows():
            code = str(row.get("Code", "") or "")
            if code not in ("P", "S"):
                continue

            results.append({
                "insider_name": str(row.get("Insider", "") or ""),
                "insider_title": str(row.get("Position", "") or "") or None,
                "transaction_type": code,
                "shares": _safe_float(row.get("Shares")),
                "price": _safe_float(row.get("Price")),
                "transaction_date": _parse_date(row.get("Date")),
                "source_filing": str(accession),
            })

    logger.info(f"Form 4: {t} → {len(results)} trades (P/S)")
    return results


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_date(value: Any) -> str | None:
    if value is None:
        return None
    try:
        from datetime import date

        import pandas as pd

        if isinstance(value, (date, pd.Timestamp)):
            return value.isoformat()[:10]  # "2026-06-15"
        return str(value)[:10]
    except (TypeError, ValueError):
        return None
