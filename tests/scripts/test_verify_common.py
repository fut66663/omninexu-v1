"""Tests for scripts/verify/_common.py shared utilities."""

import json
from unittest.mock import patch


class TestLoadAnchors:
    def test_load_anchors_returns_dict_when_file_exists(self, tmp_path):
        """_load_anchors() returns anchor data from JSON file."""
        import scripts.verify._common as common

        anchor_path = tmp_path / "anchor_revenue.json"
        anchor_path.write_text(
            json.dumps({"anchors": {"AAPL": 416161000000.0, "MSFT": 281724000000.0}}),
            encoding="utf-8",
        )

        with patch.object(common, "_ANCHOR_PATH", anchor_path):
            result = common._load_anchors()
            assert result == {"AAPL": 416161000000.0, "MSFT": 281724000000.0}

    def test_load_anchors_returns_empty_when_file_missing(self, tmp_path):
        """_load_anchors() returns {} when file does not exist."""
        import scripts.verify._common as common

        nonexistent = tmp_path / "nonexistent.json"

        with patch.object(common, "_ANCHOR_PATH", nonexistent):
            result = common._load_anchors()
            assert result == {}

    def test_load_anchors_returns_empty_when_no_anchors_key(self, tmp_path):
        """_load_anchors() returns {} when 'anchors' key is missing."""
        import scripts.verify._common as common

        anchor_path = tmp_path / "anchor_revenue.json"
        anchor_path.write_text(
            json.dumps({"something_else": [1, 2, 3]}),
            encoding="utf-8",
        )

        with patch.object(common, "_ANCHOR_PATH", anchor_path):
            result = common._load_anchors()
            assert result == {}


class TestLoadUniverse:
    def test_load_universe_returns_list(self, tmp_path):
        """load_universe() returns a list of company dicts."""
        from scripts.verify._common import load_universe

        universe_dir = tmp_path / "universe"
        universe_dir.mkdir()
        day_file = universe_dir / "sp500_universe_day1.json"
        day_file.write_text(
            json.dumps([
                {"ticker": "AAPL", "name": "Apple Inc."},
                {"ticker": "MSFT", "name": "Microsoft Corp"},
            ]),
            encoding="utf-8",
        )

        with patch("scripts.verify._common.UNIVERSE_DIR", universe_dir):
            result = load_universe(day=1)
            assert len(result) == 2
            assert result[0]["ticker"] == "AAPL"

    def test_load_universe_returns_empty_when_missing(self, tmp_path):
        """load_universe() returns [] when file is missing."""
        from scripts.verify._common import load_universe

        nonexistent_dir = tmp_path / "missing"

        with patch("scripts.verify._common.UNIVERSE_DIR", nonexistent_dir):
            result = load_universe(day=99)
            assert result == []


class TestConstants:
    def test_verify_tickers_is_non_empty(self):
        """VERIFY_TICKERS must contain tickers."""
        from scripts.verify._common import VERIFY_TICKERS

        assert len(VERIFY_TICKERS) >= 20
        assert "AAPL" in VERIFY_TICKERS
        assert "MSFT" in VERIFY_TICKERS
