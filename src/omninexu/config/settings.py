"""Application settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    omninexu_env: str = Field(default="development", alias="OMNINEXU_ENV")
    log_level: str = Field(default="INFO", alias="OMNINEXU_LOG_LEVEL")

    # Database
    database_url: str = Field(
        default="postgresql://omninexu:omninexu@localhost:5432/omninexu",
        alias="DATABASE_URL",
    )

    # Cache
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # SEC EDGAR
    edgar_identity: str = Field(default="omninexu@example.com", alias="EDGAR_IDENTITY")

    # FRED (Phase 1)
    fred_api_key: str | None = Field(default=None, alias="FRED_API_KEY")

    # SimFin (free API key from simfin.com — required for quarterly data)
    simfin_api_key: str | None = Field(default=None, alias="SIMFIN_API_KEY")

    # API
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    # Rate limiting is deferred to Phase 1. The setting is reserved for
    # forward-compatibility but no middleware reads it yet.
    api_rate_limit: str = Field(default="100/minute", alias="API_RATE_LIMIT")

    # ── x402 Payment (Phase 0.5) ──
    x402_enabled: bool = Field(default=False, alias="X402_ENABLED")
    x402_facilitator_url: str = Field(
        default="https://x402.org/facilitator", alias="X402_FACILITATOR_URL"
    )
    x402_network: str = Field(default="eip155:84532", alias="X402_NETWORK")
    x402_pay_to: str = Field(default="", alias="X402_PAY_TO")
    x402_free_routes: list[str] = Field(
        default_factory=lambda: ["GET /v1/health"], alias="X402_FREE_ROUTES"
    )
    cdp_api_key_id: str | None = Field(default=None, alias="CDP_API_KEY_ID")
    cdp_api_key_secret: str | None = Field(default=None, alias="CDP_API_KEY_SECRET")

    # Data — override via OMNINEXU_DATA_ROOT env var for non-Windows or custom paths
    omninexu_data_root: str = Field(
        default="./OmniNexuData", alias="OMNINEXU_DATA_ROOT"
    )

    @property
    def is_development(self) -> bool:
        """Return True when running in development mode."""
        return self.omninexu_env.lower() == "development"

    @property
    def is_production(self) -> bool:
        """Return True when running in production mode."""
        return self.omninexu_env.lower() == "production"


# Global settings instance
settings = Settings()
