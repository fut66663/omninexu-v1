"""Tests for insider trading application service."""

from datetime import date
from unittest.mock import MagicMock

from omninexu.application.insider import build_insider_summary
from omninexu.domain.insider import InsiderTrade


def _make_trades(types: list[str] = None) -> list[InsiderTrade]:
    """Build InsiderTrade objects with given transaction types."""
    if types is None:
        types = ["S", "S", "P"]
    return [
        InsiderTrade(
            ticker="AAPL", insider_name=f"Insider {i}",
            insider_title="Officer", transaction_type=tx,
            shares=1000.0 * (i + 1), price=195.0,
            transaction_date=date(2025, 6, i + 1),
            source_filing=f"ACC-{i:04d}",
        )
        for i, tx in enumerate(types)
    ]


class TestBuildInsiderSummary:
    """Unit tests for build_insider_summary()."""

    def test_returns_none_when_no_trades(self):
        repo = MagicMock()
        repo.get_trades.return_value = []
        assert build_insider_summary("AAPL", repo) is None

    def test_net_shares_calculation(self):
        """P=+buy, S=-sell, option exercise filtered out."""
        repo = MagicMock()
        repo.get_trades.return_value = _make_trades(["S", "S", "P"])

        result = build_insider_summary("AAPL", repo)
        assert result is not None
        # Shares: S -1000, S -2000, P +3000 → net = 0
        assert result.net_shares_90d == 0.0
        assert result.transaction_count_90d == 3

    def test_all_sales_net_negative(self):
        repo = MagicMock()
        repo.get_trades.return_value = _make_trades(["S", "S"])

        result = build_insider_summary("AAPL", repo)
        assert result is not None
        assert result.net_shares_90d < 0
        assert result.transaction_count_90d == 2

    def test_all_purchases_net_positive(self):
        repo = MagicMock()
        repo.get_trades.return_value = _make_trades(["P", "P", "P"])

        result = build_insider_summary("AAPL", repo)
        assert result is not None
        assert result.net_shares_90d > 0

    def test_recent_transactions_capped_at_20(self):
        repo = MagicMock()
        repo.get_trades.return_value = _make_trades(["S"] * 25)

        result = build_insider_summary("AAPL", repo)
        assert result is not None
        assert len(result.recent_transactions) == 20

    def test_transaction_fields_preserved(self):
        repo = MagicMock()
        repo.get_trades.return_value = _make_trades(["P"])

        result = build_insider_summary("AAPL", repo)
        assert result is not None
        tx = result.recent_transactions[0]
        assert tx.insider_name == "Insider 0"
        assert tx.transaction_type == "P"
        assert tx.shares == 1000.0

    def test_non_ps_transaction_type_neutral(self):
        """Non-P/S types (award 'A', option exercise 'O') don't affect net shares.

        Branch coverage for insider.py:32→36 — when transaction_type is
        neither 'P' nor 'S', the trade is counted in total count but its
        shares do not affect net_shares_90d.
        """
        repo = MagicMock()
        repo.get_trades.return_value = _make_trades(["P", "A", "S"])

        result = build_insider_summary("AAPL", repo)
        assert result is not None
        # P=+1000, A=+0 (neutral), S=-3000 → net = -2000
        assert result.net_shares_90d == -2000.0
        assert result.transaction_count_90d == 3
        # Award trade should still appear in recent_transactions
        types = [t.transaction_type for t in result.recent_transactions]
        assert "A" in types

    def test_skips_trades_with_none_transaction_date(self):
        """Transactions with transaction_date=None should be skipped (line 36-37)."""
        trades_with_none_date = [
            InsiderTrade(
                ticker="AAPL", insider_name="Has Date",
                insider_title="Officer", transaction_type="P",
                shares=1000.0, price=195.0,
                transaction_date=date(2025, 6, 15),
                source_filing="ACC-001",
            ),
            InsiderTrade(
                ticker="AAPL", insider_name="No Date",
                insider_title="Officer", transaction_type="P",
                shares=500.0, price=190.0,
                transaction_date=None,  # This one should be skipped
                source_filing="ACC-002",
            ),
        ]

        repo = MagicMock()
        repo.get_trades.return_value = trades_with_none_date

        result = build_insider_summary("AAPL", repo)
        assert result is not None
        assert result.transaction_count_90d == 1
        assert result.recent_transactions[0].insider_name == "Has Date"
        # net_shares should still count the skipped trade
        assert result.net_shares_90d == 1500.0
