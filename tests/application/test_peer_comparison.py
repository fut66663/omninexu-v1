"""Tests for peer comparison builder."""

from datetime import date

from omninexu.application.peer_comparison import (
    MIN_PEER_COUNT,
    PEER_COMPARISON_CONCEPTS,
    _find_fact_value,
    build_peer_comparison,
)
from omninexu.domain.company import Company, IndustryClassification
from omninexu.domain.financials import FinancialFact

CONCEPT_TO_KEY = {"Revenue": "revenue", "NetIncome": "net_income"}


def _make_fact(ticker: str, concept: str, value: float) -> FinancialFact:
    """Helper to build a FinancialFact."""
    return FinancialFact(
        ticker=ticker,
        fiscal_year=2025,
        fiscal_period="FY",
        report_date=date(2025, 9, 27),
        concept=concept,
        value=value,
    )


def test_build_peer_comparison_returns_none_with_insufficient_peers():
    """Fewer than MIN_PEER_COUNT companies should return None."""
    company = Company(
        ticker="AAPL",
        cik="0000320193",
        name="Apple Inc.",
        industry=IndustryClassification(gics_sub_industry="Semiconductors"),
    )
    peers = [company]

    result = build_peer_comparison(
        "AAPL",
        "Semiconductors",
        peers,
        CONCEPT_TO_KEY,
        lambda _ticker: [_make_fact("AAPL", "Revenue", 100.0)],
    )
    assert result is None


def test_build_peer_comparison_skips_when_target_missing_concept():
    """If the target company lacks a concept, that metric is skipped."""
    target = Company(
        ticker="AAPL",
        cik="0000320193",
        name="Apple Inc.",
        industry=IndustryClassification(gics_sub_industry="Semiconductors"),
    )
    peer1 = Company(
        ticker="MSFT",
        cik="0000789019",
        name="Microsoft Corp",
        industry=IndustryClassification(gics_sub_industry="Semiconductors"),
    )

    def fact_provider(ticker: str) -> list[FinancialFact]:
        if ticker == "AAPL":
            return [_make_fact("AAPL", "NetIncome", 50.0)]
        return [
            _make_fact(ticker, "Revenue", 100.0),
            _make_fact(ticker, "NetIncome", 50.0),
        ]

    result = build_peer_comparison(
        "AAPL",
        "Semiconductors",
        [target, peer1],
        CONCEPT_TO_KEY,
        fact_provider,
    )

    assert result is not None
    assert "revenue_rank" not in result
    assert "net_income_rank" in result


def test_build_peer_comparison_returns_none_when_all_peers_missing_values():
    """If no peer has values for any configured concept, return None."""
    target = Company(
        ticker="AAPL",
        cik="0000320193",
        name="Apple Inc.",
        industry=IndustryClassification(gics_sub_industry="Semiconductors"),
    )
    peer1 = Company(
        ticker="MSFT",
        cik="0000789019",
        name="Microsoft Corp",
        industry=IndustryClassification(gics_sub_industry="Semiconductors"),
    )

    result = build_peer_comparison(
        "AAPL",
        "Semiconductors",
        [target, peer1],
        CONCEPT_TO_KEY,
        lambda _ticker: [],
    )
    assert result is None


def test_build_peer_comparison_ignores_target_as_peer():
    """The target ticker should be excluded from peer values but included in ranking."""
    target = Company(
        ticker="AAPL",
        cik="0000320193",
        name="Apple Inc.",
        industry=IndustryClassification(gics_sub_industry="Semiconductors"),
    )
    peer1 = Company(
        ticker="MSFT",
        cik="0000789019",
        name="Microsoft Corp",
        industry=IndustryClassification(gics_sub_industry="Semiconductors"),
    )

    def fact_provider(ticker: str) -> list[FinancialFact]:
        values = {
            "AAPL": [_make_fact("AAPL", "Revenue", 200.0)],
            "MSFT": [_make_fact("MSFT", "Revenue", 100.0)],
        }
        return values.get(ticker, [])

    result = build_peer_comparison(
        "AAPL",
        "Semiconductors",
        [target, peer1],
        CONCEPT_TO_KEY,
        fact_provider,
    )

    assert result is not None
    assert result["revenue_total_peers"] == 2  # target + one peer
    assert result["revenue_rank"] == 1  # AAPL 200 > MSFT 100


def test_find_fact_value_returns_first_match():
    """_find_fact_value should return the first matching non-None value."""
    facts = [
        _make_fact("AAPL", "Revenue", 100.0),
        _make_fact("AAPL", "Revenue", 200.0),
    ]
    assert _find_fact_value(facts, "Revenue") == 100.0


def test_find_fact_value_returns_none_when_missing():
    """_find_fact_value should return None when concept is absent."""
    facts = [_make_fact("AAPL", "NetIncome", 50.0)]
    assert _find_fact_value(facts, "Revenue") is None


def test_peer_comparison_concepts_list_not_empty():
    """Ensure configured peer comparison concepts are non-empty."""
    assert PEER_COMPARISON_CONCEPTS
    assert MIN_PEER_COUNT >= 2


def test_build_peer_comparison_skips_unknown_concept_key(monkeypatch):
    """Concepts missing from concept_to_key should be skipped."""
    target = Company(
        ticker="AAPL",
        cik="0000320193",
        name="Apple Inc.",
        industry=IndustryClassification(gics_sub_industry="Semiconductors"),
    )
    peer1 = Company(
        ticker="MSFT",
        cik="0000789019",
        name="Microsoft Corp",
        industry=IndustryClassification(gics_sub_industry="Semiconductors"),
    )

    monkeypatch.setattr(
        "omninexu.application.peer_comparison.PEER_COMPARISON_CONCEPTS",
        ["Revenue", "UnknownConcept"],
    )

    result = build_peer_comparison(
        "AAPL",
        "Semiconductors",
        [target, peer1],
        CONCEPT_TO_KEY,
        lambda _ticker: [_make_fact(_ticker, "Revenue", 100.0)],
    )

    assert result is not None
    assert "revenue_rank" in result
    assert "unknownconcept_rank" not in result


def test_build_peer_comparison_peer_missing_value_returns_none():
    """If a peer lacks a value and total drops below MIN_PEER_COUNT, skip metric."""
    target = Company(
        ticker="AAPL",
        cik="0000320193",
        name="Apple Inc.",
        industry=IndustryClassification(gics_sub_industry="Semiconductors"),
    )
    peer1 = Company(
        ticker="MSFT",
        cik="0000789019",
        name="Microsoft Corp",
        industry=IndustryClassification(gics_sub_industry="Semiconductors"),
    )

    def fact_provider(ticker: str) -> list[FinancialFact]:
        if ticker == "AAPL":
            return [_make_fact("AAPL", "Revenue", 100.0)]
        return []  # MSFT has no Revenue

    result = build_peer_comparison(
        "AAPL",
        "Semiconductors",
        [target, peer1],
        CONCEPT_TO_KEY,
        fact_provider,
    )

    # Only target value remains -> below MIN_PEER_COUNT -> metric skipped.
    assert result is None


def test_build_peer_comparison_target_value_missing_for_one_concept():
    """If target lacks one concept, only that metric is skipped."""
    target = Company(
        ticker="AAPL",
        cik="0000320193",
        name="Apple Inc.",
        industry=IndustryClassification(gics_sub_industry="Semiconductors"),
    )
    peer1 = Company(
        ticker="MSFT",
        cik="0000789019",
        name="Microsoft Corp",
        industry=IndustryClassification(gics_sub_industry="Semiconductors"),
    )

    def fact_provider(ticker: str) -> list[FinancialFact]:
        if ticker == "AAPL":
            return [_make_fact("AAPL", "NetIncome", 50.0)]
        return [
            _make_fact(ticker, "Revenue", 100.0),
            _make_fact(ticker, "NetIncome", 50.0),
        ]

    result = build_peer_comparison(
        "AAPL",
        "Semiconductors",
        [target, peer1],
        CONCEPT_TO_KEY,
        fact_provider,
    )

    assert result is not None
    assert "revenue_rank" not in result
    assert "net_income_rank" in result
