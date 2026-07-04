"""Peer comparison builder for company context."""

from collections.abc import Callable
from typing import Any

import pandas as pd

from omninexu.application.ranking import industry_rank
from omninexu.domain.company import Company
from omninexu.domain.financials import FinancialFact

PEER_COMPARISON_CONCEPTS = ["Revenue", "NetIncome"]
MIN_PEER_COUNT = 2


def build_peer_comparison(
    target_ticker: str,
    sub_industry: str,
    peers: list[Company],
    concept_to_key: dict[str, str],
    fact_provider: Callable[[str], list[FinancialFact]],
) -> dict[str, Any] | None:
    """Build peer comparison ranks within the same GICS sub-industry.

    Returns ``None`` when there are fewer than two peers or no comparable
    values for the configured concepts.
    """
    if len(peers) < MIN_PEER_COUNT:
        return None

    peer_facts = {peer.ticker: fact_provider(peer.ticker) for peer in peers}
    comparison: dict[str, Any] = {}

    for concept in PEER_COMPARISON_CONCEPTS:
        key = concept_to_key.get(concept)
        if key is None:
            continue

        target_value = _find_fact_value(peer_facts.get(target_ticker, []), concept)
        if target_value is None:
            continue

        values = []
        industries = []
        for peer in peers:
            if peer.ticker == target_ticker:
                continue
            value = _find_fact_value(peer_facts.get(peer.ticker, []), concept)
            if value is None:
                continue
            values.append(value)
            industries.append(sub_industry)

        values.append(target_value)
        industries.append(sub_industry)

        if len(values) < MIN_PEER_COUNT:
            continue

        rank = industry_rank(
            pd.Series(values),
            pd.Series(industries),
            sub_industry,
        )
        comparison[f"{key}_rank"] = rank
        comparison[f"{key}_total_peers"] = len(values)

    return comparison if comparison else None


def _find_fact_value(
    facts: list[FinancialFact],
    concept: str,
) -> float | None:
    """Return the value for a concept, or None if missing."""
    for fact in facts:
        if fact.concept == concept and fact.value is not None:
            return float(fact.value)
    return None
