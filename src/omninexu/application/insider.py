"""Build insider trading summary from repository data."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

from omninexu.infrastructure.repositories.insider_repo import InsiderRepository


def build_insider_summary(
    ticker: str, repo: InsiderRepository, days: int = 90
) -> Any:
    """Build an InsiderSummary with net shares and recent transactions.

    Returns None when no insider trades exist in the database.
    """
    from omninexu.api.schemas.company import InsiderSummary, InsiderTransaction  # noqa: E402

    trades = repo.get_trades(ticker, days=days)
    if not trades:
        return None

    recent = []
    net_shares = 0.0
    for t in trades:
        shares = t.shares or 0.0
        if t.transaction_type == "P":
            net_shares += shares
        elif t.transaction_type == "S":
            net_shares -= shares

        # transaction_date is required by Pydantic schema
        if t.transaction_date is None:
            continue

        recent.append(
            InsiderTransaction(
                insider_name=t.insider_name,
                insider_title=t.insider_title,
                transaction_type=t.transaction_type,
                shares=shares,
                price=t.price,
                transaction_date=t.transaction_date,
            )
        )

    # Cap at 20 most recent
    recent = recent[:20]

    return InsiderSummary(
        recent_transactions=recent,
        net_shares_90d=net_shares,
        transaction_count_90d=len(recent),
        source="SEC Form-4",
    )
