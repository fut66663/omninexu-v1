"""Tests for quarterly (10-Q) parsing — statement types & edge cases.

Covers: income / balance / cashflow statements, missing concepts,
deduplication, empty DataFrames, and ticker normalization.
"""

from datetime import date

import pandas as pd
import pytest

from omninexu.domain.financials import FinancialFact
from omninexu.infrastructure.clients.edgar_parser import statement_to_facts


def _qdf(concepts, cols, dims=None):
    """Minimal quarterly statement DataFrame."""
    n = len(concepts)
    data = {"concept": concepts, "label": [f"L_{c[:20]}" for c in concepts]}
    for col_name, col_vals in cols.items():
        data[col_name] = col_vals
    data["dimension"] = dims or [False] * n
    data["is_breakdown"] = [False] * n
    return pd.DataFrame(data)


# ══════════════════════════════════════════════════════════════════════
# INCOME STATEMENT
# ══════════════════════════════════════════════════════════════════════

def test_10q_income_two_concepts_two_years():
    df = _qdf(
        ["us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax",
         "us-gaap_NetIncomeLoss"],
        {"2025-03-31 (Q1)": [124.3e9, 34.63e9],
         "2024-03-31 (Q1)": [119.6e9, 30.0e9]},
    )
    facts = statement_to_facts(df, ticker="AAPL", statement_type="income",
                               report_date=date(2025, 3, 31), source_filing="10-Q")
    assert len(facts) == 4
    revenue = [f for f in facts if f.concept == "Revenue"]
    assert len(revenue) == 2
    q2025 = next(f for f in revenue if f.fiscal_year == 2025)
    assert q2025.value == pytest.approx(124.3e9)
    assert q2025.fiscal_period == "Q1"


# ══════════════════════════════════════════════════════════════════════
# BALANCE SHEET
# ══════════════════════════════════════════════════════════════════════

def test_10q_balance_all_three_concepts():
    df = _qdf(
        ["us-gaap_Assets", "us-gaap_Liabilities", "us-gaap_StockholdersEquity"],
        {"2025-03-31 (Q1)": [350e9, 280e9, 70e9]},
    )
    facts = statement_to_facts(df, ticker="AAPL", statement_type="balance",
                               report_date=date(2025, 3, 31), source_filing="10-Q")
    assert {f.concept for f in facts} == {"TotalAssets", "TotalLiabilities", "StockholdersEquity"}
    assert all(f.fiscal_period == "Q1" for f in facts)


# ══════════════════════════════════════════════════════════════════════
# CASH FLOW
# ══════════════════════════════════════════════════════════════════════

def test_10q_cashflow_two_quarters():
    df = _qdf(
        ["us-gaap_NetCashProvidedByUsedInOperatingActivities"],
        {"2025-06-30 (Q2)": [30e9], "2024-06-30 (Q2)": [28e9]},
    )
    facts = statement_to_facts(df, ticker="AAPL", statement_type="cashflow",
                               report_date=date(2025, 6, 30), source_filing="10-Q")
    assert {(f.fiscal_year, f.fiscal_period) for f in facts} == {(2025, "Q2"), (2024, "Q2")}


# ══════════════════════════════════════════════════════════════════════
# EDGE CASES
# ══════════════════════════════════════════════════════════════════════

def test_missing_gross_profit_skipped_gracefully():
    df = _qdf(
        ["us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax",
         "us-gaap_NetIncomeLoss"],
        {"2025-06-30 (Q2)": [210e9, 55e9]},
    )
    facts = statement_to_facts(df, ticker="AAPL", statement_type="income",
                               report_date=date(2025, 6, 30), source_filing="10-Q")
    concepts = {f.concept for f in facts}
    assert "Revenue" in concepts and "NetIncome" in concepts
    assert "GrossProfit" not in concepts
    assert len(facts) == 2


def test_empty_df():
    assert statement_to_facts(pd.DataFrame(), ticker="AAPL", statement_type="income",
                              report_date=date(2025, 3, 31), source_filing="10-Q") == []


def test_no_date_columns():
    df = pd.DataFrame({"concept": ["us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax"]})
    assert statement_to_facts(df, ticker="AAPL", statement_type="income",
                              report_date=date(2025, 3, 31), source_filing="10-Q") == []


def test_unknown_statement_type():
    df = _qdf(["us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax"],
              {"2025-03-31 (Q1)": [100.0]})
    assert statement_to_facts(df, ticker="AAPL", statement_type="unknown",
                              report_date=date(2025, 3, 31), source_filing="10-Q") == []


def test_ticker_lowercased():
    df = _qdf(["us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax"],
              {"2025-03-31 (Q1)": [100.0]})
    facts = statement_to_facts(df, ticker="aapl", statement_type="income",
                               report_date=date(2025, 3, 31), source_filing="10-Q")
    assert facts[0].ticker == "AAPL"


def test_deduplicate_same_year_period():
    """Two columns → same (2025, Q1) → keep first, skip second."""
    df = _qdf(
        ["us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax"],
        {"2025-03-31 (Q1)": [124.3e9], "2025-03-31 (Q1) restated": [124.300001e9]},
    )
    facts = statement_to_facts(df, ticker="AAPL", statement_type="income",
                               report_date=date(2025, 3, 31), source_filing="10-Q")
    revenue = [f for f in facts if f.concept == "Revenue"]
    assert len(revenue) == 1
    assert revenue[0].value == pytest.approx(124.3e9)


def test_all_facts_are_financial_fact_instances():
    df = _qdf(
        ["us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax",
         "us-gaap_NetIncomeLoss"],
        {"2025-03-31 (Q1)": [124.3e9, 34.63e9]},
    )
    facts = statement_to_facts(df, ticker="aapl", statement_type="income",
                               report_date=date(2025, 3, 31), source_filing="10-Q")
    assert len(facts) > 0
    assert all(isinstance(f, FinancialFact) for f in facts)
    assert all(f.ticker == "AAPL" for f in facts)
    assert all(f.unit == "USD" for f in facts)
