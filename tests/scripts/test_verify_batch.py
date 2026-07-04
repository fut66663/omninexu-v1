"""Tests for the verify batch orchestrator."""

from unittest.mock import patch


class TestVerifyDay:
    """Tests for scripts.verify.batch.verify_day()."""

    @staticmethod
    def _mock_pass_result():
        return {"level": "L1", "pass": True, "issues": [], "dummy": 0}

    @staticmethod
    def _mock_fail_result():
        return {"level": "L1", "pass": False, "issues": ["something wrong"], "dummy": 0}

    def test_returns_false_when_no_universe(self):
        """verify_day should return False when universe is empty."""
        with patch(
            "scripts.verify.batch.load_universe", return_value=[]
        ):
            from scripts.verify.batch import verify_day

            result = verify_day(day=99)

        assert result is False

    def test_returns_true_when_all_checks_pass(self):
        """verify_day should return True when all three checks pass."""
        universe = [{"ticker": "AAPL", "name": "Apple Inc."}]
        with patch(
            "scripts.verify.batch.load_universe", return_value=universe
        ), patch(
            "scripts.verify.batch.check_l1", return_value=self._mock_pass_result()
        ), patch(
            "scripts.verify.batch.check_l2", return_value=self._mock_pass_result()
        ), patch(
            "scripts.verify.batch.check_l3", return_value=self._mock_pass_result()
        ):
            from scripts.verify.batch import verify_day

            result = verify_day(day=1)

        assert result is True

    def test_returns_false_when_any_check_fails(self):
        """verify_day should return False when at least one check fails."""
        universe = [{"ticker": "AAPL", "name": "Apple Inc."}]
        with patch(
            "scripts.verify.batch.load_universe", return_value=universe
        ), patch(
            "scripts.verify.batch.check_l1", return_value=self._mock_pass_result()
        ), patch(
            "scripts.verify.batch.check_l2", return_value=self._mock_fail_result()
        ), patch(
            "scripts.verify.batch.check_l3", return_value=self._mock_pass_result()
        ):
            from scripts.verify.batch import verify_day

            result = verify_day(day=1)

        assert result is False

    def test_handles_check_exception_gracefully(self):
        """verify_day should catch exceptions from individual checks and continue."""
        universe = [{"ticker": "AAPL", "name": "Apple Inc."}]
        with patch(
            "scripts.verify.batch.load_universe", return_value=universe
        ), patch(
            "scripts.verify.batch.check_l1",
            side_effect=RuntimeError("DB connection failed"),
        ), patch(
            "scripts.verify.batch.check_l2", return_value=self._mock_pass_result()
        ), patch(
            "scripts.verify.batch.check_l3", return_value=self._mock_pass_result()
        ):
            from scripts.verify.batch import verify_day

            result = verify_day(day=1)

        assert result is False  # L1 raised, so overall fails
