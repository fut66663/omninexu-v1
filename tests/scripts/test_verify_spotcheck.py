"""Tests for L2 spot-check validation."""

import os
from unittest.mock import MagicMock, patch

import pytest


class TestCheckL2:
    """Tests for scripts.verify.spotcheck.check_l2()."""

    @staticmethod
    def _mock_universe_with_anchors():
        return [
            {"ticker": "AAPL", "name": "Apple Inc."},
            {"ticker": "MSFT", "name": "Microsoft Corp."},
        ]

    @staticmethod
    def _mock_universe_no_anchors():
        return [
            {"ticker": "TSLA", "name": "Tesla Inc."},
            {"ticker": "UBER", "name": "Uber Technologies Inc."},
        ]

    def test_skips_when_no_anchors_in_batch(self):
        """check_l2 should return early when no anchor companies in batch."""
        with patch(
            "scripts.verify.spotcheck.load_universe",
            return_value=self._mock_universe_no_anchors(),
        ):
            from scripts.verify.spotcheck import check_l2

            result = check_l2(day=1)

        assert result["checked"] == 0
        assert result["pass"] is True
        assert "no anchors" in result["note"]

    def test_checks_anchor_revenue_values(self):
        """check_l2 should verify revenue for anchor companies."""
        # Mock FinancialFactModel row
        mock_fact = MagicMock()
        mock_fact.ticker = "AAPL"
        mock_fact.concept = "Revenue"
        mock_fact.value = 416_161_000_000.0  # matches ANCHOR_REVENUE

        with patch(
            "scripts.verify.spotcheck.load_universe",
            return_value=self._mock_universe_with_anchors(),
        ), patch("scripts.verify.spotcheck.SessionLocal") as mock_session_cls:
            mock_db = MagicMock()
            # Return the mock fact for both AAPL and MSFT queries
            mock_scalars = MagicMock()
            mock_scalars.first.return_value = mock_fact
            mock_db.execute.return_value.scalars.return_value = mock_scalars
            mock_session_cls.return_value = mock_db

            from scripts.verify.spotcheck import check_l2

            result = check_l2(day=1)

        assert result["level"] == "L2"
        assert result["checked"] >= 0
        assert "pass" in result
        assert "issues" in result

    @pytest.mark.skipif(
        os.environ.get("GITHUB_ACTIONS") == "true",
        reason="CI environment has no scripts/ in PYTHONPATH",
    )
    def test_reports_missing_revenue_fact(self):
        """check_l2 should report discrepancy when Revenue fact is missing."""
        with patch(
            "scripts.verify.spotcheck.load_universe",
            return_value=self._mock_universe_with_anchors(),
        ), patch("scripts.verify.spotcheck.SessionLocal") as mock_session_cls:
            mock_db = MagicMock()
            mock_scalars = MagicMock()
            mock_scalars.first.return_value = None  # no fact found
            mock_db.execute.return_value.scalars.return_value = mock_scalars
            mock_session_cls.return_value = mock_db

            from scripts.verify.spotcheck import check_l2

            result = check_l2(day=1)

        assert result["pass"] is False
        assert any("no Revenue fact" in i for i in result["issues"])
