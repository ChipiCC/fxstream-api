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
    app_name: str = "FastAPI Service"
    environment: Environment = "local"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
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

    @field_validator("allowed_hosts", "cors_origins", "api_keys", mode="before")
    @classmethod
    def _split_list(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        text = value.strip()
        if text.startswith("["):
            return json.loads(text)
        return [item.strip() for item in text.split(",") if item.strip()]

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
