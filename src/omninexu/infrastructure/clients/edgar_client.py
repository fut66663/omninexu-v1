"""SEC EDGAR client wrapper."""

from datetime import date
from typing import Any

import httpx
from edgar import Company, CompanyNotFoundError, set_identity

from omninexu.config.settings import settings
from omninexu.domain.financials import FinancialFact
from omninexu.infrastructure.clients.edgar_historical import (
    _cache_filing_html,
    fetch_historical_filings,
)
from omninexu.infrastructure.clients.edgar_parser import statement_to_facts
from omninexu.observability import (
    EdgarRateLimitError,
    TickerNotFoundError,
    get_logger,
)

logger = get_logger(__name__)


class EdgarClient:
    """Wrapper around edgartools for SEC EDGAR data access."""

    def __init__(self, identity: str = settings.edgar_identity):
        self.identity = identity
        set_identity(identity)

    def get_company(self, ticker: str) -> Company:
        """Get edgartools Company object."""
        return Company(ticker.upper())

    # ── Public API ──────────────────────────────────────────────────────

    def get_financial_facts(
        self, ticker: str, num_filings: int = 1, form: str = "10-K"
    ) -> list[FinancialFact]:
        """Download SEC filings and parse into standardized financial facts.

        Args:
            ticker: Stock ticker symbol (e.g. ``"AAPL"``).
            num_filings: Number of latest filings to fetch.
                Default ``1`` (single filing — backward compatible).
            form: SEC form type — ``"10-K"`` (annual) or ``"10-Q"`` (quarterly).
                Default ``"10-K"``.
        """
        all_facts: list[FinancialFact] = []

        if num_filings == 1:
            stmts, rd, src = self._fetch_filing_statements(ticker, form=form)
            all_facts = self._parse_statements_to_facts(stmts, ticker, rd, src)
        else:
            company = self.get_company(ticker)
            filings_data = fetch_historical_filings(
                company, ticker, num_filings, self._parse_report_date, form=form,
            )
            for stmts, rd, src in filings_data:
                all_facts.extend(self._parse_statements_to_facts(stmts, ticker, rd, src))

        logger.info(f"Parsed {len(all_facts)} facts for {ticker} across {num_filings} filing(s)")
        return all_facts

    def get_company_info(self, ticker: str) -> dict[str, Any]:
        """Get basic company info (ticker, cik, name, sic)."""
        try:
            company = self.get_company(ticker)
            return {
                "ticker": ticker.upper(),
                "cik": company.cik,
                "name": company.name,
                "sic": company.sic,
            }
        except CompanyNotFoundError as exc:
            logger.warning(f"Ticker not found in EDGAR: {ticker}")
            raise TickerNotFoundError(f"{ticker}") from exc
        except httpx.HTTPError as exc:
            logger.warning(f"EDGAR request failed for {ticker}: {exc}")
            raise EdgarRateLimitError() from exc

    # ── Private helpers ──────────────────────────────────────────────────

    def _fetch_filing_statements(
        self, ticker: str, *, form: str = "10-K"
    ) -> tuple[dict[str, Any], date, str]:
        """Download single latest SEC filing and return (statements, report_date, source)."""
        import pandas as pd

        t = ticker.upper()
        logger.info(f"Fetching {form} statements for {t}")

        try:
            company = self.get_company(t)
            filing = company.get_filings(form=form).latest(1)
            tenk = filing.obj()
        except CompanyNotFoundError as exc:
            logger.warning(f"Ticker not found in EDGAR: {t}")
            raise TickerNotFoundError(f"{t}") from exc
        except httpx.HTTPError as exc:
            logger.warning(f"EDGAR request failed for {t}: {exc}")
            raise EdgarRateLimitError() from exc

        report_date = self._parse_report_date(filing.period_of_report)
        source_filing = filing.accession_no or form
        _cache_filing_html(
            t,
            report_date,
            filing,
            sub_dir=getattr(filing, "form", form),
        )

        statements: dict[str, pd.DataFrame] = {}
        for stype, attr in [
            ("income", "income_statement"),
            ("balance", "balance_sheet"),
            ("cashflow", "cash_flow_statement"),
        ]:
            stmt = getattr(tenk, attr, None)
            if stmt is not None:
                statements[stype] = stmt.to_dataframe()
        return statements, report_date, source_filing

    def _parse_statements_to_facts(
        self,
        statements: dict[str, Any],
        ticker: str,
        report_date: date,
        source_filing: str,
    ) -> list[FinancialFact]:
        """Parse statement DataFrames into FinancialFact domain objects."""
        facts: list[FinancialFact] = []
        for stype, df in statements.items():
            facts.extend(
                statement_to_facts(
                    df,
                    ticker=ticker.upper(),
                    statement_type=stype,
                    report_date=report_date,
                    source_filing=source_filing,
                )
            )
        return facts

    @staticmethod
    def _parse_report_date(raw: str | None) -> date:
        """Parse period_of_report string into a date."""
        if raw is None:
            raise ValueError("period_of_report is missing from EDGAR filing")
        return date.fromisoformat(raw)
