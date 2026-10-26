"""Application configuration.

Settings are read from environment variables and, outside production, from a
`.env.local` file in the working directory (missing files are ignored). Real
environment variables always take precedence over the file, and the file takes
precedence over the field defaults. In production no dotfile is read at all.
Nested values can be provided with a double underscore, e.g. `POSTGRES__HOST`.
List-valued settings (`ALLOWED_HOSTS`, `CORS_ORIGINS`, `API_KEYS`) accept either
a comma-separated string or a JSON array.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Annotated, Any, Literal
from urllib.parse import quote

from pydantic import AliasChoices, Field, computed_field, field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    NoDecode,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from core.symbols import normalize_symbol

DOTENV_FILE = ".env.local"
"""Local settings file: read outside production, ignored when it does not exist."""


def _is_production_process() -> bool:
    """Whether this process runs in production, decided before sources are built.

    The dotenv file cannot be consulted here (that is the decision being made),
    so only the real process environment is inspected. In production the
    environment identifier is always injected by the platform.
    """
    return any(
        key.upper() == "ENVIRONMENT" and value.strip().lower() == "production"
        for key, value in os.environ.items()
    )


Environment = Literal["local", "staging", "production"]
SslMode = Literal["disable", "allow", "prefer", "require", "verify-ca", "verify-full"]

# List fields must not be JSON-decoded eagerly by pydantic-settings so that the
# `_split_list` validator can accept both CSV and JSON forms.
CsvList = Annotated[list[str], NoDecode]


class Settings(BaseSettings):
    """Strongly-typed application settings."""

    model_config = SettingsConfigDict(
        env_file=DOTENV_FILE,
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Order the sources: init arguments, env vars, then `.env.local`.

        The dotenv source is dropped in production so deployments configure
        everything through real environment variables (or mounted secrets).
        """
        sources: list[PydanticBaseSettingsSource] = [init_settings, env_settings]
        if not _is_production_process():
            sources.append(dotenv_settings)
        sources.append(file_secret_settings)
        return tuple(sources)

    # --- Application ---
    app_name: str = "FXStream API"
    environment: Environment = "local"
    debug: bool = False
    api_v1_prefix: str = "/v1"
    docs_enabled: bool = True

    # --- HTTP server ---
    host: str = "0.0.0.0"  # noqa: S104 - containers bind all interfaces
    port: int = 8000

    # --- Observability ---
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_json: bool = True
    metrics_enabled: bool = True
    metrics_path: str = "/metrics"

    # --- Security ---
    allowed_hosts: CsvList = Field(default_factory=lambda: ["*"])
    security_headers_enabled: bool = True
    cors_origins: CsvList = Field(default_factory=list)
    cors_allow_credentials: bool = False
    cors_allow_methods: CsvList = Field(default_factory=lambda: ["*"])
    cors_allow_headers: CsvList = Field(default_factory=lambda: ["*"])
    # When empty, authentication is disabled (intended for local development).
    api_keys: CsvList = Field(default_factory=list)
    rate_limit_enabled: bool = False
    rate_limit_requests: int = Field(default=100, ge=1)
    rate_limit_window_seconds: int = Field(default=60, ge=1)

    # --- Market data ---
    market_data_enabled: bool = True
    binance_symbols: CsvList = Field(default_factory=lambda: ["BTC/USDT"])
    frankfurter_symbols: CsvList = Field(default_factory=lambda: ["EUR/USD"])
    binance_ws_url: str = "wss://stream.binance.com:9443/stream"
    frankfurter_base_url: str = "https://api.frankfurter.dev/v1"
    frankfurter_poll_seconds: int = Field(default=3600, ge=1)
    provider_request_timeout_seconds: float = Field(default=10.0, gt=0)
    provider_stale_seconds: dict[str, int] = Field(
        default_factory=lambda: {"binance": 10, "frankfurter": 129600}
    )
    provider_failure_threshold: int = Field(default=3, ge=1)
    provider_backoff_initial_seconds: float = Field(default=1.0, gt=0)
    provider_backoff_max_seconds: float = Field(default=60.0, gt=0)

    # --- Quotes ---
    default_spread_bps: int = Field(default=10, ge=0)
    spreads_bps: dict[str, int] = Field(default_factory=dict)
    quote_ttl_seconds: int = Field(default=30, ge=1)
    quote_retention_seconds: int = Field(default=300, ge=0)
    price_decimals: int = Field(default=8, ge=0, le=18)
    price_decimals_by_symbol: dict[str, int] = Field(default_factory=dict)

    # --- Candles ---
    candles_enabled: bool = True
    candle_flush_seconds: int = Field(default=60, ge=1)

    # --- Database ---
    # A full DSN wins over the individual POSTGRES_* fields. It must use the
    # asyncpg driver (`postgresql+asyncpg://`); a bare `postgresql://` is upgraded.
    database_url_override: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DATABASE_URL", "database_url_override"),
    )
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"  # noqa: S105 - local-only placeholder default
    postgres_db: str = "app"
    postgres_ssl: SslMode | None = None
    db_echo: bool = False
    db_pool_size: int = Field(default=5, ge=1)
    db_max_overflow: int = Field(default=10, ge=0)
    db_pool_recycle_seconds: int = Field(default=1800, ge=-1)
    db_pool_timeout_seconds: int = Field(default=30, ge=1)
    db_statement_timeout_ms: int = Field(default=0, ge=0)

    @field_validator(
        "allowed_hosts",
        "cors_origins",
        "api_keys",
        "binance_symbols",
        "frankfurter_symbols",
        mode="before",
    )
    @classmethod
    def _split_list(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        text = value.strip()
        if text.startswith("["):
            return json.loads(text)
        return [item.strip() for item in text.split(",") if item.strip()]

    @field_validator("binance_symbols", "frankfurter_symbols")
    @classmethod
    def _normalize_symbols(cls, value: list[str]) -> list[str]:
        return [normalize_symbol(symbol) for symbol in value]

    @field_validator("spreads_bps", "price_decimals_by_symbol")
    @classmethod
    def _normalize_symbol_keys(cls, value: dict[str, int]) -> dict[str, int]:
        return {normalize_symbol(symbol): item for symbol, item in value.items()}

    @field_validator("spreads_bps")
    @classmethod
    def _validate_spreads(cls, value: dict[str, int]) -> dict[str, int]:
        if any(spread < 0 or spread > 10000 for spread in value.values()):
            raise ValueError("spreads must be between 0 and 10000 bps")
        return value

    @field_validator("price_decimals_by_symbol")
    @classmethod
    def _validate_decimals(cls, value: dict[str, int]) -> dict[str, int]:
        if any(decimals < 0 or decimals > 18 for decimals in value.values()):
            raise ValueError("price decimals must be between 0 and 18")
        return value

    @field_validator("provider_stale_seconds")
    @classmethod
    def _validate_stale_thresholds(cls, value: dict[str, int]) -> dict[str, int]:
        if any(threshold <= 0 for threshold in value.values()):
            raise ValueError("stale thresholds must be positive")
        return value

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        """Async SQLAlchemy connection URL (asyncpg driver)."""
        if self.database_url_override:
            url = self.database_url_override
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return url
        # credentials are URL-encoded so passwords containing reserved characters
        # (@ : / ? # &) do not corrupt the DSN
        user = quote(self.postgres_user, safe="")
        password = quote(self.postgres_password, safe="")
        url = (
            f"postgresql+asyncpg://{user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
        if self.postgres_ssl:
            url = f"{url}?ssl={self.postgres_ssl}"
        return url

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def symbols(self) -> list[str]:
        """All configured symbols, preserving order without duplicates."""
        return list(dict.fromkeys([*self.binance_symbols, *self.frankfurter_symbols]))

    def symbols_for_provider(self, provider: str) -> list[str]:
        if provider == "binance":
            return list(self.binance_symbols)
        if provider == "frankfurter":
            return list(self.frankfurter_symbols)
        return []

    def stale_seconds_for(self, provider: str) -> int:
        return self.provider_stale_seconds.get(provider, 60)

    def spread_bps_for(self, symbol: str) -> int:
        return self.spreads_bps.get(normalize_symbol(symbol), self.default_spread_bps)

    def price_decimals_for(self, symbol: str) -> int:
        return self.price_decimals_by_symbol.get(normalize_symbol(symbol), self.price_decimals)

    @model_validator(mode="after")
    def _validate_market(self) -> Settings:
        overlap = set(self.binance_symbols) & set(self.frankfurter_symbols)
        if overlap:
            joined = ", ".join(sorted(overlap))
            raise ValueError(f"symbols cannot be served by two providers: {joined}")
        # An env override should not accidentally drop the other provider's
        # threshold and mark that provider permanently stale.
        self.provider_stale_seconds.setdefault("binance", 10)
        self.provider_stale_seconds.setdefault("frankfurter", 129600)
        return self

    @model_validator(mode="after")
    def _guard_production(self) -> Settings:
        """Fail fast when production runs with insecure defaults."""
        if not self.is_production:
            return self
        problems: list[str] = []
        if self.debug:
            problems.append("DEBUG must be false")
        if self.docs_enabled:
            problems.append("DOCS_ENABLED must be false")
        if self.postgres_password == "postgres":  # noqa: S105 - default sentinel
            problems.append("POSTGRES_PASSWORD must be overridden")
        if not self.api_keys:
            problems.append("API_KEYS must be set")
        if "*" in self.allowed_hosts:
            problems.append("ALLOWED_HOSTS must be explicit")
        if problems:
            raise ValueError("insecure production configuration: " + "; ".join(problems))
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached `Settings` instance (safe to use as a FastAPI dependency)."""
    return Settings()
