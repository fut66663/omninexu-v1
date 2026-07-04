"""Tests for quarterly (10-Q) financial statement parsing — core.

Focus: prove fiscal_period isolation — quarterly data must NEVER contaminate
annual data.  The unique constraint is (company_id, fiscal_year, fiscal_period,
concept); a misidentified period would silently overwrite the wrong row.
"""

from datetime import date

import pandas as pd

from omninexu.infrastructure.clients.edgar_parser import (
    _date_columns,
    _infer_fiscal_period,
    statement_to_facts,
)

# ══════════════════════════════════════════════════════════════════════
# ISOLATION — quarterly must not leak into annual
# ══════════════════════════════════════════════════════════════════════

def _qdf(concepts, values, cols, dims=None):
    """Build a minimal statement DataFrame with quarterly columns."""
    n = len(concepts)
    data = {"concept": concepts, "label": [f"Label_{c}" for c in concepts]}
    for col_name, col_vals in cols.items():
        data[col_name] = col_vals
    data["dimension"] = dims or [False] * n
    data["is_breakdown"] = [False] * n
    return pd.DataFrame(data)


def test_quarterly_fact_never_has_fy_period():
    """Q1 suffix → fiscal_period='Q1', NEVER 'FY'.

    If a Q1 column gets period='FY', it would collide with annual data
    on the (company_id, year, period, concept) unique constraint.
    """
    df = _qdf(
        ["us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax"],
        None,
        {"2025-03-31 (Q1)": [124.3e9], "2024-03-31 (Q1)": [119.6e9]},
    )
    facts = statement_to_facts(df, ticker="AAPL", statement_type="income",
                               report_date=date(2025, 3, 31), source_filing="10-Q")
    for f in facts:
        assert f.fiscal_period != "FY", (
            f"CONTAMINATION: {f.concept} got period='{f.fiscal_period}' — should be Q1"
        )
        assert f.fiscal_period == "Q1"


def test_fy_and_q1_same_year_are_distinct_keys():
    """(2025, FY) and (2025, Q1) must produce two separate records.

    If they collapsed to the same key, the DB upsert would overwrite one.
    """
    df = _qdf(
        ["us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax"],
        None,
        {"2025-09-27 (FY)": [416.2e9], "2025-03-31 (Q1)": [124.3e9]},
    )
    facts = statement_to_facts(df, ticker="AAPL", statement_type="income",
                               report_date=date(2025, 9, 27), source_filing="10-K")
    revenue = [f for f in facts if f.concept == "Revenue"]
    assert len(revenue) == 2
    keys = {(f.fiscal_year, f.fiscal_period) for f in revenue}
    assert keys == {(2025, "FY"), (2025, "Q1")}, f"Wrong keys: {keys}"


def test_mixed_fy_q1_q2_each_independent():
    """Three period suffixes → three distinct (year, period) pairs."""
    df = _qdf(
        ["us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax"],
        None,
        {"2025-09-27 (FY)": [416.2e9], "2025-06-30 (Q2)": [210e9],
         "2025-03-31 (Q1)": [105e9]},
    )
    facts = statement_to_facts(df, ticker="AAPL", statement_type="income",
                               report_date=date(2025, 9, 27), source_filing="10-K")
    periods = {(f.fiscal_year, f.fiscal_period) for f in facts}
    assert periods == {(2025, "FY"), (2025, "Q2"), (2025, "Q1")}


def test_source_filing_10q_vs_10k():
    """source_filing is the provenance label — 10-Q must not be confused with 10-K."""
    df = _qdf(
        ["us-gaap_NetIncomeLoss"], None,
        {"2025-03-31 (Q1)": [34.6e9]},
    )
    q_facts = statement_to_facts(df, ticker="AAPL", statement_type="income",
                                 report_date=date(2025, 3, 31), source_filing="10-Q")
    assert all(f.source_filing == "10-Q" for f in q_facts)

    k_df = _qdf(
        ["us-gaap_NetIncomeLoss"], None,
        {"2025-09-27 (FY)": [112e9]},
    )
    k_facts = statement_to_facts(k_df, ticker="AAPL", statement_type="income",
                                 report_date=date(2025, 9, 27), source_filing="10-K")
    assert all(f.source_filing == "10-K" for f in k_facts)


# ══════════════════════════════════════════════════════════════════════
# PERIOD INFERENCE
# ══════════════════════════════════════════════════════════════════════

def test_infer_fiscal_period_q1_q2_q3():
    assert _infer_fiscal_period("2025-03-31 (Q1)") == "Q1"
    assert _infer_fiscal_period("2025-06-30 (Q2)") == "Q2"
    assert _infer_fiscal_period("2025-09-30 (Q3)") == "Q3"


def test_infer_fiscal_period_fy_default():
    assert _infer_fiscal_period("2025-09-27 (FY)") == "FY"
    assert _infer_fiscal_period("2025-09-27") == "FY"


def test_infer_fiscal_period_case_insensitive():
    assert _infer_fiscal_period("2025-03-31 (q1)") == "Q1"
    assert _infer_fiscal_period("2025-06-30 (Q2)") == "Q2"


def test_date_columns_detect_all_periods():
    df = pd.DataFrame(columns=[
        "concept", "2025-03-31 (Q1)", "2025-06-30 (Q2)",
        "2025-09-30 (Q3)", "2025-12-31 (FY)",
    ])
    date_cols = _date_columns(df)
    assert len(date_cols) == 4
