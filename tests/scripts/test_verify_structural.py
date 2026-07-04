"""Tests for L1 structural validation."""

from unittest.mock import MagicMock, patch


class TestCheckL1:
    """Tests for scripts.verify.structural.check_l1()."""

    @staticmethod
    def _mock_universe():
        return [
            {"ticker": "AAPL", "name": "Apple Inc."},
            {"ticker": "MSFT", "name": "Microsoft Corp."},
            {"ticker": "GOOGL", "name": "Alphabet Inc."},
        ]

    def test_returns_expected_keys(self):
        """check_l1 should return a dict with required keys."""
        with patch(
            "scripts.verify.structural.load_universe",
            return_value=self._mock_universe(),
        ), patch("scripts.verify.structural.SessionLocal") as mock_session_cls:
            mock_db = MagicMock()
            mock_db.scalar.return_value = 3  # all 3 companies in DB
            mock_db.execute.return_value.mappings.return_value.all.return_value = [
                {"ticker": "AAPL", "cnt": 10},
                {"ticker": "MSFT", "cnt": 8},
                {"ticker": "GOOGL", "cnt": 6},
            ]
            mock_session_cls.return_value = mock_db

            from scripts.verify.structural import check_l1

            result = check_l1(day=1)

        assert result["level"] == "L1"
        assert result["companies_expected"] == 3
        assert "company_coverage_pct" in result
        assert "gics_coverage_pct" in result
        assert "pass" in result
        assert "issues" in result

    def test_all_pass_when_coverage_full(self):
        """check_l1 should report pass=True when all checks pass."""
        with patch(
            "scripts.verify.structural.load_universe",
            return_value=self._mock_universe(),
        ), patch("scripts.verify.structural.SessionLocal") as mock_session_cls:
            mock_db = MagicMock()
            mock_db.scalar.side_effect = [3, 3]  # companies, gics
            mock_db.execute.return_value.mappings.return_value.all.return_value = [
                {"ticker": "AAPL", "cnt": 10},
                {"ticker": "MSFT", "cnt": 8},
                {"ticker": "GOOGL", "cnt": 6},
            ]
            mock_session_cls.return_value = mock_db

            from scripts.verify.structural import check_l1

            result = check_l1(day=1)

        assert result["pass"] is True
        assert len(result["issues"]) == 0

    def test_fails_when_company_coverage_incomplete(self):
        """check_l1 should report pass=False when companies are missing."""
        with patch(
            "scripts.verify.structural.load_universe",
            return_value=self._mock_universe(),
        ), patch("scripts.verify.structural.SessionLocal") as mock_session_cls:
            mock_db = MagicMock()
            mock_db.scalar.side_effect = [2, 2]  # only 2 of 3 companies
            mock_db.execute.return_value.mappings.return_value.all.return_value = [
                {"ticker": "AAPL", "cnt": 10},
                {"ticker": "MSFT", "cnt": 8},
            ]
            mock_session_cls.return_value = mock_db

            from scripts.verify.structural import check_l1

            result = check_l1(day=1)

        assert result["pass"] is False
        assert any("Missing" in i for i in result["issues"])

    def test_handles_empty_universe(self):
        """check_l1 should report failure for an empty universe (no data to validate)."""
        with patch(
            "scripts.verify.structural.load_universe", return_value=[]
        ), patch("scripts.verify.structural.SessionLocal") as mock_session_cls:
            mock_db = MagicMock()
            mock_db.scalar.return_value = 0
            mock_db.execute.return_value.mappings.return_value.all.return_value = []
            mock_session_cls.return_value = mock_db

            from scripts.verify.structural import check_l1

            result = check_l1(day=99)

        assert result["pass"] is False  # 0% coverage fails all thresholds
        assert result["companies_expected"] == 0
        assert len(result["issues"]) > 0
