"""Multi-filing historical SEC filing downloader.

Used by :class:`EdgarClient` when ``num_filings > 1`` to fetch N years
of financial statements in a single batch.
"""

from datetime import date
from typing import Any

import httpx
from edgar import Company, CompanyNotFoundError

from omninexu.config import data_paths
from omninexu.observability import EdgarRateLimitError, TickerNotFoundError, get_logger

logger = get_logger(__name__)


def fetch_historical_filings(
    company: Company,
    ticker: str,
    num_filings: int,
    parse_date: Any,
    *,
    form: str = "10-K",
) -> list[tuple[dict[str, Any], date, str]]:
    """Download *N* latest SEC filings and return their statement DataFrames.

    Args:
        company: edgartools Company object.
        ticker: Stock ticker symbol.
        num_filings: Number of latest filings to fetch.
        parse_date: Callable to parse ``period_of_report`` into a ``date``.
        form: SEC form type — ``"10-K"`` (annual) or ``"10-Q"`` (quarterly).

    Each 10-K includes 2-3 comparison-year columns, so ``N=2`` covers ~6 years.
    Each 10-Q includes current quarter + same quarter last year.

    Deduplicates by ``period_of_report`` — when a 10-K/A amendment shares
    the same period as the original, only the first (most recent) is kept.
    Individual filing failures are warned and skipped.
    """
    t = ticker.upper()
    logger.info(f"Fetching {num_filings} {form} filings for {t}")

    try:
        filings = company.get_filings(form=form).latest(num_filings)
    except CompanyNotFoundError as exc:
        raise TickerNotFoundError(f"{t}") from exc
    except httpx.HTTPError as exc:
        raise EdgarRateLimitError() from exc

    results: list[tuple[dict[str, Any], date, str]] = []
    seen: set[str] = set()

    for filing in filings:
        period = filing.period_of_report or ""
        if period in seen:
            continue
        seen.add(period)

        try:
            tenk = filing.obj()
        except Exception as exc:
            logger.warning(f"Parse failed {filing.accession_no} for {t}: {exc}")
            continue

        report_date = parse_date(filing.period_of_report)
        source = filing.accession_no or form
        _cache_filing_html(
            t,
            report_date,
            filing,
            sub_dir=getattr(filing, "form", form),
        )

        stmts: dict[str, Any] = {}
        for stype, attr in [
            ("income", "income_statement"),
            ("balance", "balance_sheet"),
            ("cashflow", "cash_flow_statement"),
        ]:
            stmt = getattr(tenk, attr, None)
            if stmt is not None:
                stmts[stype] = stmt.to_dataframe()
        results.append((stmts, report_date, source))

    logger.info(f"Fetched {len(results)}/{num_filings} {form} filings for {t}")
    return results


def _cache_filing_html(
    ticker: str, report_date: date, filing: Any, *, sub_dir: str = "10-K"
) -> None:
    """Cache raw SEC filing HTML to disk. Best-effort.

    Args:
        ticker: Stock ticker (no CIK suffix).
        report_date: Filing report date.
        filing: edgartools Filing object with ``.text()``.
        sub_dir: Form type directory (``"10-K"``, ``"13F-HR"``, ``"Form-4"``, etc.).
    """
    # Resolve the base directory in type-first layout (e.g. 10-K/AAPL/).
    _form_map = {
        "10-K": data_paths.raw_sec_10k,
        "10-K/A": data_paths.raw_sec_10ka,
        "10-Q": data_paths.raw_sec_10q,
        "13F-HR": data_paths.raw_sec_13f,
        "Form-4": data_paths.raw_sec_form4,
    }
    sub_dir_str = sub_dir if isinstance(sub_dir, str) else "10-K"
    base = _form_map.get(sub_dir_str, data_paths.raw_sec / sub_dir_str)
    raw_dir = base / ticker / report_date.isoformat()
    html_path = raw_dir / "filing.html"
    if html_path.exists():
        return
    try:
        raw_dir.mkdir(parents=True, exist_ok=True)
        html_path.write_text(filing.text(), encoding="utf-8")
    except OSError as exc:
        logger.warning(f"Failed to cache raw filing for {ticker}: {exc}")
