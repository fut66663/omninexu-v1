"""Tests for financial statement parsing."""

from datetime import date

import pandas as pd
import pytest

from omninexu.domain.financials import FinancialFact
from omninexu.infrastructure.clients.edgar_parser import (
    STATEMENT_CONCEPTS,
    _date_columns,
    _extract_value,
    _find_matching_row,
    _infer_fiscal_period,
    _infer_fiscal_year,
    _is_date_column,
    statement_to_facts,
)


def test_statement_concepts_has_core_metrics():
    """Core financial metrics should be defined for all three statements."""
    assert "income" in STATEMENT_CONCEPTS
    assert "balance" in STATEMENT_CONCEPTS
    assert "cashflow" in STATEMENT_CONCEPTS

    assert "Revenue" in STATEMENT_CONCEPTS["income"]
    assert "NetIncome" in STATEMENT_CONCEPTS["income"]
    assert "TotalAssets" in STATEMENT_CONCEPTS["balance"]
    assert "OperatingCashFlow" in STATEMENT_CONCEPTS["cashflow"]


def test_revenue_concepts_include_primary_and_fallback():
    """Revenue should have the primary US-GAAP concept and a fallback."""
    revenue_candidates = STATEMENT_CONCEPTS["income"]["Revenue"]
    assert "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax" in revenue_candidates
    assert "us-gaap_Revenues" in revenue_candidates


def test_date_columns_detects_statement_date_columns():
    """Date columns should be identified correctly."""
    df = pd.DataFrame(columns=["concept", "label", "2025-09-27 (FY)", "2024-09-28 (FY)", "level"])
    assert _date_columns(df) == ["2025-09-27 (FY)", "2024-09-28 (FY)"]


def test_infer_fiscal_period_from_column_names():
    """Fiscal period should be inferred from column suffixes."""
    assert _infer_fiscal_period("2025-09-27 (FY)") == "FY"
    assert _infer_fiscal_period("2025-06-30 (Q1)") == "Q1"
    assert _infer_fiscal_period("2025-03-31 (Q2)") == "Q2"
    assert _infer_fiscal_period("2024-12-31 (Q3)") == "Q3"


def _make_income_df() -> pd.DataFrame:
    """Build a minimal income statement DataFrame matching edgartools shape."""
    return pd.DataFrame(
        {
            "concept": [
                "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax",
                "us-gaap_NetIncomeLoss",
            ],
            "label": ["Net sales", "Net income"],
            "2025-09-27 (FY)": [416161000000.0, 112010000000.0],
            "2024-09-28 (FY)": [391035000000.0, 93736000000.0],
            "dimension": [False, False],
            "is_breakdown": [False, False],
        }
    )


def test_statement_to_facts_extracts_revenue():
    """statement_to_facts should extract Revenue facts."""
    df = _make_income_df()
    facts = statement_to_facts(
        df,
        ticker="AAPL",
        statement_type="income",
        report_date=date(2025, 9, 27),
        source_filing="10-K",
    )

    revenue_facts = [f for f in facts if f.concept == "Revenue"]
    assert len(revenue_facts) == 2
    fy2025 = next(f for f in revenue_facts if f.fiscal_year == 2025)
    assert fy2025.value == pytest.approx(416161000000.0)
    assert fy2025.fiscal_period == "FY"
    assert fy2025.statement_type == "income"


def test_statement_to_facts_infers_fiscal_year_from_columns():
    """Each fact should use the year from its statement column, not the report date."""
    df = _make_income_df()
    facts = statement_to_facts(
        df,
        ticker="AAPL",
        statement_type="income",
        report_date=date(2025, 9, 27),
        source_filing="10-K",
    )

    by_year = {f.fiscal_year: f for f in facts if f.concept == "NetIncome"}
    assert 2025 in by_year
    assert 2024 in by_year
    assert by_year[2025].value == pytest.approx(112010000000.0)
    assert by_year[2024].value == pytest.approx(93736000000.0)


def test_statement_to_facts_skips_breakdown_rows():
    """Breakdown rows (product/segment) should be skipped."""
    df = pd.DataFrame(
        {
            "concept": [
                "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax",
                "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax",
            ],
            "label": ["Net sales", "iPhone"],
            "2025-09-27 (FY)": [416161000000.0, 209586000000.0],
            "dimension": [False, True],
            "is_breakdown": [False, False],
        }
    )

    facts = statement_to_facts(
        df,
        ticker="AAPL",
        statement_type="income",
        report_date=date(2025, 9, 27),
        source_filing="10-K",
    )

    assert len(facts) == 1
    assert facts[0].value == pytest.approx(416161000000.0)


def test_statement_to_facts_handles_missing_concept():
    """Missing concepts should result in no facts for that concept."""
    df = pd.DataFrame(
        {
            "concept": ["us-gaap_SomeOtherConcept"],
            "label": ["Other"],
            "2025-09-27 (FY)": [100.0],
            "dimension": [False],
            "is_breakdown": [False],
        }
    )

    facts = statement_to_facts(
        df,
        ticker="AAPL",
        statement_type="income",
        report_date=date(2025, 9, 27),
        source_filing="10-K",
    )

    assert facts == []


def test_statement_to_facts_returns_empty_for_empty_df():
    """Empty DataFrame should return empty list."""
    facts = statement_to_facts(
        pd.DataFrame(),
        ticker="AAPL",
        statement_type="income",
        report_date=date(2025, 9, 27),
        source_filing="10-K",
    )
    assert facts == []


def test_statement_to_facts_returns_financial_fact_instances():
    """All returned items should be FinancialFact instances."""
    df = _make_income_df()
    facts = statement_to_facts(
        df,
        ticker="aapl",
        statement_type="income",
        report_date=date(2025, 9, 27),
        source_filing="10-K",
    )

    assert all(isinstance(f, FinancialFact) for f in facts)
    assert all(f.ticker == "AAPL" for f in facts)
    assert all(f.unit == "USD" for f in facts)


def test_is_date_column_rejects_invalid_strings():
    """Invalid date-like strings should not be treated as date columns."""
    assert _is_date_column("not-a-date") is False
    assert _is_date_column("2025-09") is False
    assert _is_date_column("2025/09/27") is False
    assert _is_date_column("") is False


def test_date_columns_skips_non_string_columns():
    """Non-string column names should be ignored."""
    df = pd.DataFrame(columns=["concept", 2025, "2025-09-27 (FY)"])
    assert _date_columns(df) == ["2025-09-27 (FY)"]


def test_infer_fiscal_year_fallback_to_report_date():
    """When the column has no parseable date, use the report date year."""
    report_date = date(2025, 9, 27)
    assert _infer_fiscal_year("bad-column", report_date, "FY") == 2025


def test_extract_value_handles_nan_and_non_numeric():
    """NaN and non-numeric cells should return None."""
    assert _extract_value(float("nan")) is None
    assert _extract_value(None) is None
    assert _extract_value("not-a-number") is None
    assert _extract_value(123.0) == pytest.approx(123.0)


def test_statement_to_facts_unknown_statement_type():
    """Unknown statement types should return an empty list."""
    df = _make_income_df()
    facts = statement_to_facts(
        df,
        ticker="AAPL",
        statement_type="unknown",
        report_date=date(2025, 9, 27),
        source_filing="10-K",
    )
    assert facts == []


def test_statement_to_facts_no_date_columns():
    """DataFrames without date columns should return an empty list."""
    df = pd.DataFrame({"concept": ["us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax"], "value": [100.0]})
    facts = statement_to_facts(
        df,
        ticker="AAPL",
        statement_type="income",
        report_date=date(2025, 9, 27),
        source_filing="10-K",
    )
    assert facts == []


def test_find_matching_row_returns_none_when_no_match():
    """No matching consolidated row should return None."""
    df = pd.DataFrame(
        {
            "concept": ["us-gaap_SomeOtherConcept"],
            "2025-09-27 (FY)": [100.0],
            "dimension": [False],
            "is_breakdown": [False],
        }
    )
    assert _find_matching_row(df, ["us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax"]) is None


def test_find_matching_row_skips_breakdown_rows():
    """Rows marked as breakdown/dimension should be skipped."""
    df = pd.DataFrame(
        {
            "concept": ["us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax"],
            "2025-09-27 (FY)": [100.0],
            "dimension": [True],
            "is_breakdown": [False],
        }
    )
    assert _find_matching_row(df, ["us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax"]) is None


def test_statement_to_facts_skips_nan_values():
    """Date columns containing NaN for a concept should be skipped."""
    df = pd.DataFrame(
        {
            "concept": ["us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax"],
            "label": ["Net sales"],
            "2025-09-27 (FY)": [float("nan")],
            "dimension": [False],
            "is_breakdown": [False],
        }
    )

    facts = statement_to_facts(
        df,
        ticker="AAPL",
        statement_type="income",
        report_date=date(2025, 9, 27),
        source_filing="10-K",
    )

    assert facts == []


def test_statement_to_facts_deduplicates_same_fiscal_period():
    """Multiple columns resolving to the same fiscal period should be deduplicated."""
    df = pd.DataFrame(
        {
            "concept": ["us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax"],
            "label": ["Net sales"],
            "2025-09-27 (FY)": [416161000000.0],
            "2025-09-27 (FY) restated": [416161000001.0],
            "dimension": [False],
            "is_breakdown": [False],
        }
    )

    facts = statement_to_facts(
        df,
        ticker="AAPL",
        statement_type="income",
        report_date=date(2025, 9, 27),
        source_filing="10-K",
    )

    revenue_facts = [f for f in facts if f.concept == "Revenue"]
    assert len(revenue_facts) == 1
    assert revenue_facts[0].value == pytest.approx(416161000000.0)
