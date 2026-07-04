"""SimFin data adapter — bulk historical financials from local CSV cache.

Supports both annual and quarterly data via a single internal pipeline,
parameterized by :class:`_Variant`.  Public API methods preserve the
existing interface for backward compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
from typing import Any

import pandas as pd
import simfin as sf
from simfin.names import *  # noqa: F403

from omninexu.domain.financials import FinancialFact
from omninexu.observability import get_logger

logger = get_logger(__name__)

# ── concept mappings ─────────────────────────────────────────────────

# SimFin column → (OmniNexu concept, statement_type)
_COMPANY_MAP: dict[str, tuple[str, str]] = {
    "Revenue": ("Revenue", "income"),
    "Net Income": ("NetIncome", "income"),
    "Gross Profit": ("GrossProfit", "income"),
    "Operating Income (Loss)": ("OperatingIncome", "income"),
    "Total Assets": ("TotalAssets", "balance"),
    "Total Liabilities": ("TotalLiabilities", "balance"),
    "Total Equity": ("StockholdersEquity", "balance"),
    "Net Cash from Operating Activities": ("OperatingCashFlow", "cashflow"),
}

# Banks lack Gross Profit (non-bank business model)
_BANK_MAP: dict[str, tuple[str, str]] = {
    k: v for k, v in _COMPANY_MAP.items() if k != "Gross Profit"
}

_BANKS: frozenset[str] = frozenset({
    "JPM", "BAC", "WFC", "C", "GS", "MS", "USB", "PNC", "TFC", "BK",
})


# ── variant config ──────────────────────────────────────────────────


@dataclass(frozen=True)
class _Variant:
    """Configuration for a single data variant (annual / quarterly)."""

    name: str           # "annual" | "quarterly"
    source: str         # "simfin" | "simfin_quarterly"
    default_period: str  # "FY" | "Q1"
    income: pd.DataFrame | None = None
    balance: pd.DataFrame | None = None
    cashflow: pd.DataFrame | None = None
    income_banks: pd.DataFrame | None = None
    balance_banks: pd.DataFrame | None = None
    cashflow_banks: pd.DataFrame | None = None


# ── adapter ─────────────────────────────────────────────────────────


class SimFinAdapter:
    """Bulk historical financial data from SimFin local CSV cache.

    Supports annual and quarterly data through a unified internal pipeline.
    """

    def __init__(self, data_dir: str | None = None) -> None:
        from omninexu.config import data_paths

        self._data_dir = data_dir or str(data_paths.raw_simfin)
        self._loaded = False
        self._quarterly_failed = False
        self._annual = _Variant("annual", "simfin", "FY")
        self._quarterly = _Variant("quarterly", "simfin_quarterly", "Q1")

    # ── Public API ─────────────────────────────────────────────────

    def get_financial_facts(
        self, ticker: str, start_year: int = 2020
    ) -> list[FinancialFact]:
        """Return FinancialFacts for *ticker* from SimFin **annual** data."""
        self._load()
        return self._get_facts(ticker, start_year, self._annual)

    def get_quarterly_facts(
        self, ticker: str, start_year: int = 2020
    ) -> list[FinancialFact]:
        """Return FinancialFacts for *ticker* from SimFin **quarterly** data.

        Uses ``source="simfin_quarterly"`` to prevent collision with annual.
        """
        if not self._load_quarterly():
            logger.warning(
                "SimFin quarterly data not available — skipping %s", ticker
            )
            return []
        return self._get_facts(ticker, start_year, self._quarterly)

    def get_company_info(self, ticker: str) -> dict[str, Any]:
        """Get basic company info from SimFin companies table."""
        sf.set_data_dir(self._data_dir)
        df = sf.load_companies(market="us")
        simfin_ticker = self._ticker_simfin(ticker)
        if simfin_ticker not in df.index:
            return {"ticker": ticker.upper(), "cik": "", "name": "", "sic": ""}
        row = df.loc[simfin_ticker]
        return {
            "ticker": ticker.upper(),
            "cik": str(row.get("CIK", "") or ""),
            "name": str(row.get("Company Name", "") or ""),
            "sic": str(row.get("IndustryId", "") or ""),
        }

    # ── Internal: data loading ─────────────────────────────────────

    def _load(self) -> None:
        """Lazy-load annual SimFin CSVs (once)."""
        if self._loaded:
            return
        sf.set_data_dir(self._data_dir)
        self._annual = _Variant(
            "annual", "simfin", "FY",
            income=sf.load_income(variant="annual", market="us"),
            balance=sf.load_balance(variant="annual", market="us"),
            cashflow=sf.load_cashflow(variant="annual", market="us"),
            income_banks=sf.load_income_banks(variant="annual", market="us"),
            balance_banks=sf.load_balance_banks(variant="annual", market="us"),
            cashflow_banks=sf.load_cashflow_banks(variant="annual", market="us"),
        )
        self._loaded = True
        logger.info("SimFin annual CSVs loaded")

    def _load_quarterly(self) -> bool:
        """Lazy-load quarterly SimFin CSVs.  Returns False if unavailable."""
        if self._quarterly_failed:
            return False
        if self._quarterly.income is not None:
            return True

        sf.set_data_dir(self._data_dir)
        from omninexu.config.settings import settings

        if settings.simfin_api_key:
            sf.set_api_key(settings.simfin_api_key)

        try:
            self._quarterly = _Variant(
                "quarterly", "simfin_quarterly", "Q1",
                income=sf.load_income(variant="quarterly", market="us"),
                balance=sf.load_balance(variant="quarterly", market="us"),
                cashflow=sf.load_cashflow(variant="quarterly", market="us"),
                income_banks=sf.load_income_banks(variant="quarterly", market="us"),
                balance_banks=sf.load_balance_banks(variant="quarterly", market="us"),
                cashflow_banks=sf.load_cashflow_banks(variant="quarterly", market="us"),
            )
            logger.info("SimFin quarterly CSVs loaded")
            return True
        except Exception as exc:
            logger.warning("SimFin quarterly data unavailable: %s", exc)
            self._quarterly_failed = True
            return False

    # ── Internal: unified extraction pipeline ───────────────────────

    def _get_facts(
        self, ticker: str, start_year: int, v: _Variant
    ) -> list[FinancialFact]:
        """Extract facts for *ticker* using variant *v* (annual or quarterly)."""
        simfin_ticker = self._ticker_simfin(ticker)
        is_bank = simfin_ticker in _BANKS
        concept_map = _BANK_MAP if is_bank else _COMPANY_MAP

        facts: list[FinancialFact] = []
        for simfin_col, (concept, stype) in concept_map.items():
            for fy, period, val, rpt_date in self._extract_rows(
                simfin_ticker, simfin_col, stype, is_bank, v
            ):
                if fy is None or fy < start_year or val is None or rpt_date is None:
                    continue
                facts.append(
                    FinancialFact(
                        ticker=ticker.upper(),
                        fiscal_year=fy,
                        fiscal_period=period or v.default_period,
                        report_date=rpt_date,
                        concept=concept,
                        value=float(val),
                        unit="USD",
                        source_filing="simfin",
                        statement_type=stype,
                        source=v.source,
                    )
                )

        logger.info(
            "SimFin %s: %s → %d facts (FY%d+)",
            v.name, ticker, len(facts), start_year,
        )
        return facts

    def _extract_rows(
        self,
        ticker: str,
        col: str,
        stype: str,
        is_bank: bool,
        v: _Variant,
    ) -> list[tuple[int | None, str | None, float | None, date_type | None]]:
        """Extract (fiscal_year, period, value, report_date) tuples for a concept."""
        df = self._pick_df(stype, is_bank, v)
        if df is None or df.empty:
            return []
        if ticker not in df.index.get_level_values("Ticker"):
            return []
        subset = df.loc[ticker]
        if col not in subset.columns:
            return []

        rows: list[
            tuple[int | None, str | None, float | None, date_type | None]
        ] = []
        for idx, row in subset.iterrows():
            val = row.get(col)
            if pd.isna(val):
                continue
            fy = (
                int(row.get("Fiscal Year", 0))
                if "Fiscal Year" in row.index
                else None
            )
            period = str(row.get("Fiscal Period", v.default_period))
            rows.append((fy, period, float(val), idx))
        return rows

    @staticmethod
    def _pick_df(stype: str, is_bank: bool, v: _Variant) -> pd.DataFrame | None:
        """Return the DataFrame for *stype* from variant *v*."""
        source = (
            {"income": v.income_banks, "balance": v.balance_banks,
             "cashflow": v.cashflow_banks}
            if is_bank
            else {"income": v.income, "balance": v.balance,
                  "cashflow": v.cashflow}
        )
        return source.get(stype)

    @staticmethod
    def _ticker_simfin(ticker: str) -> str:
        """GOOGL → GOOG (SimFin only has Class C)."""
        return "GOOG" if ticker.upper() == "GOOGL" else ticker.upper()
