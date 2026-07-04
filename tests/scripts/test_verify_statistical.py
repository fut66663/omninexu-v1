"""Tests for L3 statistical validation."""

from unittest.mock import MagicMock, patch


class TestCheckL3:
    """Tests for scripts.verify.statistical.check_l3()."""

    @staticmethod
    def _mock_universe():
        return [
            {"ticker": "AAPL", "name": "Apple Inc."},
            {"ticker": "MSFT", "name": "Microsoft Corp."},
        ]

    def test_returns_expected_keys(self):
        """check_l3 should return a dict with required keys."""
        with patch(
            "scripts.verify.statistical.load_universe",
            return_value=self._mock_universe(),
        ), patch("scripts.verify.statistical.SessionLocal") as mock_session_cls:
            mock_db = MagicMock()
            mock_db.scalar.side_effect = [0, 0, 2020, 2025]
            mock_db.execute.return_value.mappings.return_value.all.return_value = [
                {"concept": "Revenue", "cnt": 5},
                {"concept": "NetIncome", "cnt": 5},
            ]
            mock_session_cls.return_value = mock_db

            from scripts.verify.statistical import check_l3

            result = check_l3(day=1)

        assert result["level"] == "L3"
        assert result["negative_revenue_count"] == 0
        assert result["negative_assets_count"] == 0
        assert "fiscal_year_range" in result
        assert "concept_summary" in result
        assert "pass" in result
        assert "issues" in result

    def test_all_pass_when_data_is_clean(self):
        """check_l3 should pass when no anomalies are found."""
        with patch(
            "scripts.verify.statistical.load_universe",
            return_value=self._mock_universe(),
        ), patch("scripts.verify.statistical.SessionLocal") as mock_session_cls:
            mock_db = MagicMock()
            mock_db.scalar.side_effect = [0, 0, 2020, 2025]  # no negatives, sane years
            mock_db.execute.return_value.mappings.return_value.all.return_value = [
                {"concept": "Revenue", "cnt": 5},
            ]
            mock_session_cls.return_value = mock_db

            from scripts.verify.statistical import check_l3

            result = check_l3(day=1)

        assert result["pass"] is True
        assert len(result["issues"]) == 0

    def test_fails_on_negative_revenue(self):
        """check_l3 should report failure when negative Revenue values exist."""
        with patch(
            "scripts.verify.statistical.load_universe",
            return_value=self._mock_universe(),
        ), patch("scripts.verify.statistical.SessionLocal") as mock_session_cls:
            mock_db = MagicMock()
            mock_db.scalar.side_effect = [3, 0, 2020, 2025]  # 3 negative revenues
            mock_db.execute.return_value.mappings.return_value.all.return_value = []
            mock_session_cls.return_value = mock_db

            from scripts.verify.statistical import check_l3

            result = check_l3(day=1)

        assert result["pass"] is False
        assert any("negative Revenue" in i for i in result["issues"])

    def test_fails_on_old_fiscal_year(self):
        """check_l3 should report failure when fiscal year is too old."""
        with patch(
            "scripts.verify.statistical.load_universe",
            return_value=self._mock_universe(),
        ), patch("scripts.verify.statistical.SessionLocal") as mock_session_cls:
            mock_db = MagicMock()
            mock_db.scalar.side_effect = [0, 0, 1999, 2025]  # min year 1999
            mock_db.execute.return_value.mappings.return_value.all.return_value = []
            mock_session_cls.return_value = mock_db

            from scripts.verify.statistical import check_l3

            result = check_l3(day=1)

        assert result["pass"] is False
        assert any("1999" in i for i in result["issues"])
