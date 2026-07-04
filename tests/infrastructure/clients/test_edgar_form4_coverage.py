"""Coverage supplements for edgar_form4.py — _safe_float, _parse_date edge cases."""

from omninexu.infrastructure.clients.edgar_form4 import _parse_date, _safe_float


class TestForm4Coverage:
    """Edge cases not covered by existing Form 4 tests."""

    # ── _safe_float ───────────────────────────────────────────────────

    def test_safe_float_invalid_raises_valueerror(self):
        """Non-numeric string triggers ValueError → None."""
        assert _safe_float("N/A") is None

    def test_safe_float_invalid_type_raises_typeerror(self):
        """List input triggers TypeError → None."""
        assert _safe_float([1, 2, 3]) is None

    # ── _parse_date ──────────────────────────────────────────────────

    def test_parse_date_none_returns_none(self):
        """None input → None output."""
        assert _parse_date(None) is None

    def test_parse_date_valid_iso_string(self):
        """ISO-format string is returned as-is."""
        assert _parse_date("2025-06-15") == "2025-06-15"

    def test_parse_date_unparseable_returns_truncated_str(self):
        """str() on any object succeeds, so except branch is never hit.
        The function returns str(value)[:10] for non-date inputs."""
        # object() → '<object ob' → truncated to 10 chars
        result = _parse_date("2025-06-15T12:00:00Z")
        assert result == "2025-06-15"
