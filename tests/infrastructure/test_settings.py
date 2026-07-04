"""Tests for application settings."""


from omninexu.config.settings import Settings


def test_is_development_true():
    """is_development should be True when env is 'development'."""
    settings = Settings(OMNINEXU_ENV="development")
    assert settings.is_development is True
    assert settings.is_production is False


def test_is_production_true():
    """is_production should be True when env is 'production'."""
    settings = Settings(OMNINEXU_ENV="production")
    assert settings.is_production is True
    assert settings.is_development is False


def test_environment_case_insensitive():
    """Environment checks should be case-insensitive."""
    settings = Settings(OMNINEXU_ENV="DEVELOPMENT")
    assert settings.is_development is True

    settings = Settings(OMNINEXU_ENV="Production")
    assert settings.is_production is True
