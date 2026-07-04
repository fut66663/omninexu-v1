"""Tests for scripts/verify/verify_all.py."""

from unittest.mock import patch


class TestFakeCache:
    """FakeCache in verify_all.py is intentionally a no-op stub.

    It returns None on get_json and does nothing on set_json/delete
    because the verification script is designed to always recompute.
    """

    def test_get_json_always_returns_none(self):
        from scripts.verify.verify_all import FakeCache

        cache = FakeCache()
        assert cache.get_json("any_key") is None
        # Even after "setting", still returns None
        cache.set_json("key", {"a": 1})
        assert cache.get_json("key") is None

    def test_set_json_does_nothing(self):
        from scripts.verify.verify_all import FakeCache

        cache = FakeCache()
        cache.set_json("x", [1, 2, 3])  # should not raise

    def test_delete_is_noop(self):
        from scripts.verify.verify_all import FakeCache

        cache = FakeCache()
        cache.delete("anything")  # should not raise


class TestMain:
    """Integration test for verify_all.main() with mocked dependencies."""

    def test_main_runs_without_errors(self):
        """main() should iterate all 20 tickers and produce a summary."""
        from scripts.verify.verify_all import TICKERS, main

        with (
            patch("scripts.verify.verify_all.SessionLocal"),
            patch("scripts.verify.verify_all.CompanyContextService") as mock_svc_cls,
        ):
            mock_svc = mock_svc_cls.return_value
            mock_svc.build_context.return_value = {
                "fundamentals": {"Revenue": {"value": 100, "unit": "USD"}},
                "longitudinal": {"Revenue_3y_cagr": 0.05},
                "peer_comparison": {"revenue_rank": 1},
                "institutional": {"top_holders": [{"name": "Vanguard"}]},
                "insider": {"transaction_count_90d": 1},
                "sources": ["10-K"],
                "confidence": "high",
                "name": "Test Inc.",
            }

            main()

            assert mock_svc.build_context.call_count == len(TICKERS)

    def test_main_handles_null_institutional(self):
        """Peer/institutional/insider can be null — should not crash."""
        from scripts.verify.verify_all import main

        with (
            patch("scripts.verify.verify_all.SessionLocal"),
            patch("scripts.verify.verify_all.CompanyContextService") as mock_svc_cls,
        ):
            mock_svc = mock_svc_cls.return_value
            mock_svc.build_context.return_value = {
                "fundamentals": {"Revenue": {"value": 100, "unit": "USD"}},
                "longitudinal": {},
                "peer_comparison": None,
                "institutional": None,
                "insider": None,
                "sources": [],
                "confidence": "low",
                "name": "Test Inc.",
            }

            main()  # should not raise
