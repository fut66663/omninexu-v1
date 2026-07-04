"""Coverage supplement for _compute_confidence — all three confidence levels."""


class TestConfidence:
    """Tests for all three _compute_confidence branches."""

    def test_confidence_high_with_5_dimensions(self):
        """5 of 5 dims filled -> 'high'."""
        from omninexu.application.company_context import CompanyContextService

        result = CompanyContextService._compute_confidence(
            fundamentals={"revenue": {"value": 100}},
            longitudinal={"revenue_cagr": 0.10},
            peer_comparison={"rank": 2},
            institutional=[{"holder": "Vanguard"}],
            insider=[{"name": "Cook"}],
        )
        assert result == "high"

    def test_confidence_medium_with_3_dimensions(self):
        """3 of 5 dims filled -> 'medium'."""
        from omninexu.application.company_context import CompanyContextService

        result = CompanyContextService._compute_confidence(
            fundamentals={"revenue": {"value": 100}},
            longitudinal={},
            peer_comparison={"rank": 2},
            institutional=[{"holder": "Vanguard"}],
            insider=None,
        )
        assert result == "medium"

    def test_confidence_medium_with_4_dimensions(self):
        """4 of 5 dims filled -> 'medium'."""
        from omninexu.application.company_context import CompanyContextService

        result = CompanyContextService._compute_confidence(
            fundamentals={"revenue": {"value": 100}},
            longitudinal={"revenue_cagr": 0.10},
            peer_comparison={"rank": 2},
            institutional=[{"holder": "Vanguard"}],
            insider=None,
        )
        assert result == "medium"

    def test_confidence_low_with_2_dimensions(self):
        """< 3 dims filled -> 'low'."""
        from omninexu.application.company_context import CompanyContextService

        result = CompanyContextService._compute_confidence(
            fundamentals=None,
            longitudinal={},
            peer_comparison={"rank": 2},
            institutional=None,
            insider=None,
        )
        assert result == "low"
