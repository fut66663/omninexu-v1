"""Parse edgartools financial statement DataFrames into domain facts."""

from datetime import date
from typing import Any

import pandas as pd

from omninexu.domain.financials import FinancialFact

# Map standardized OmniNexu concepts to candidate XBRL concepts returned by edgartools.
# edgartools 5.x uses underscore-separated concept names (e.g. us-gaap_Revenue...).
STATEMENT_CONCEPTS: dict[str, dict[str, list[str]]] = {
    "income": {
        "Revenue": [
            "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax",
            "us-gaap_Revenues",
        ],
        "NetIncome": ["us-gaap_NetIncomeLoss"],
        "EPSDiluted": ["us-gaap_EarningsPerShareDiluted"],
        "GrossProfit": ["us-gaap_GrossProfit"],
        "OperatingIncome": ["us-gaap_OperatingIncomeLoss"],
    },
    "balance": {
        "TotalAssets": ["us-gaap_Assets"],
        "TotalLiabilities": ["us-gaap_Liabilities"],
        "StockholdersEquity": ["us-gaap_StockholdersEquity"],
    },
    "cashflow": {
        "OperatingCashFlow": ["us-gaap_NetCashProvidedByUsedInOperatingActivities"],
    },
}


def _date_columns(df: pd.DataFrame) -> list[str]:
    """Return columns that represent statement dates."""
    return [col for col in df.columns if isinstance(col, str) and _is_date_column(col)]


def _is_date_column(column: str) -> bool:
    """Check if a column name starts with a YYYY-MM-DD date."""
    parts = column.split()
    if not parts:
        return False
    candidate = parts[0]
    if len(candidate) != 10 or candidate[4] != "-" or candidate[7] != "-":
        return False
    year, month, day = candidate.split("-")
    return year.isdigit() and month.isdigit() and day.isdigit()


def _infer_fiscal_period(column: str) -> str:
    """Infer fiscal period from column name suffix."""
    upper = column.upper()
    if "(FY)" in upper:
        return "FY"
    if "(Q1)" in upper:
        return "Q1"
    if "(Q2)" in upper:
        return "Q2"
    if "(Q3)" in upper:
        return "Q3"
    return "FY"


def _column_year(column: str) -> int | None:
    """Extract the year from a statement date column name.

    Column names are expected to start with ``YYYY-MM-DD`` followed by an
    optional period suffix such as ``(FY)``.
    """
    if not _is_date_column(column):
        return None
    year_str = column.split("-")[0]
    return int(year_str)


def _infer_fiscal_year(column: str, report_date: date, period: str) -> int:
    """Infer fiscal year from the statement column, falling back to report date.

    For annual reports the fiscal year usually matches the calendar year of the
    statement date. When the column does not contain a parseable date, we fall
    back to the filing's report date year.
    """
    parsed = _column_year(column)
    if parsed is not None:
        return parsed
    return report_date.year


def _extract_value(raw: Any) -> float | None:
    """Extract a numeric value from a DataFrame cell."""
    if pd.isna(raw):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _is_consolidated_row(row: pd.Series) -> bool:
    """Return True if the row represents a consolidated (non-breakdown) value."""
    dimension = row.get("dimension")
    is_breakdown = row.get("is_breakdown")
    return not bool(dimension) and not bool(is_breakdown)


def _find_matching_row(df: pd.DataFrame, candidates: list[str]) -> pd.Series | None:
    """Find the first consolidated row whose concept matches a candidate."""
    for concept in candidates:
        mask = df["concept"] == concept
        if not mask.any():
            continue
        matches = df.loc[mask]
        consolidated = matches[matches.apply(_is_consolidated_row, axis=1)]
        if not consolidated.empty:
            return consolidated.iloc[0]
    return None


def statement_to_facts(
    df: pd.DataFrame,
    ticker: str,
    statement_type: str,
    report_date: date,
    source_filing: str,
    source: str = "edgar",
) -> list[FinancialFact]:
    """Convert an edgartools statement DataFrame into FinancialFact objects."""
    if df.empty or statement_type not in STATEMENT_CONCEPTS:
        return []

    date_cols = _date_columns(df)
    if not date_cols:
        return []

    concept_map = STATEMENT_CONCEPTS[statement_type]
    facts: list[FinancialFact] = []
    seen: set[tuple[int, str, str]] = set()

    for concept_name, candidates in concept_map.items():
        row = _find_matching_row(df, candidates)
        if row is None:
            continue

        for col in date_cols:
            value = _extract_value(row.get(col))
            if value is None:
                continue

            period = _infer_fiscal_period(col)
            fiscal_year = _infer_fiscal_year(col, report_date, period)
            key = (fiscal_year, period, concept_name)
            if key in seen:
                continue
            seen.add(key)

            facts.append(
                FinancialFact(
                    ticker=ticker.upper(),
                    fiscal_year=fiscal_year,
                    fiscal_period=period,
                    report_date=report_date,
                    concept=concept_name,
                    value=value,
                    unit="USD",
                    source_filing=source_filing,
                    statement_type=statement_type,
                    source=source,
                )
            )

    return facts
