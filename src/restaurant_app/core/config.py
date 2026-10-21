"""Typed application settings loaded from environment variables."""

from enum import StrEnum
from functools import lru_cache
from typing import Literal, Self
from urllib.parse import quote, urlsplit

from pydantic import Field, PostgresDsn, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnvironment(StrEnum):
    """Supported runtime environments."""

    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Environment-backed settings with safe development defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        env_prefix="RESTAURANT_",
        extra="ignore",
        frozen=True,
        populate_by_name=True,
    )

    app_name: str = "Restaurant App V2 API"
    app_version: str = "0.1.0"
    environment: AppEnvironment = AppEnvironment.LOCAL
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    api_v1_prefix: str = "/api/v1"

    postgres_host: str = Field(default="127.0.0.1", validation_alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, ge=1, le=65535, validation_alias="POSTGRES_PORT")
    postgres_db: str = Field(default="restaurant_app", validation_alias="POSTGRES_DB")
    postgres_user: str = Field(default="restaurant_app", validation_alias="POSTGRES_USER")
    postgres_password: SecretStr = Field(
        default=SecretStr("replace-this-local-password"),
        validation_alias="POSTGRES_PASSWORD",
        repr=False,
    )
    database_echo: bool = False
    database_pool_size: int = Field(default=5, ge=1, le=50)
    database_max_overflow: int = Field(default=10, ge=0, le=100)
    database_pool_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    database_pool_recycle_seconds: int = Field(default=1800, ge=60)

    cors_origins: list[str] = Field(default_factory=list)

    @field_validator("api_v1_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        """Keep the future versioned API prefix unambiguous."""

        normalized = value.strip()
        if not normalized.startswith("/"):
            raise ValueError("api_v1_prefix must start with '/'")
        if normalized != "/" and normalized.endswith("/"):
            normalized = normalized.rstrip("/")
        return normalized

    @field_validator("postgres_host", "postgres_db", "postgres_user")
    @classmethod
    def reject_blank_postgres_components(cls, value: str) -> str:
        """Reject ambiguous connection components before constructing the DSN."""

        normalized = value.strip()
        if not normalized:
            raise ValueError("PostgreSQL connection components must not be blank")
        return normalized

    @field_validator("postgres_password")
    @classmethod
    def reject_blank_postgres_password(cls, value: SecretStr) -> SecretStr:
        """Require an explicit non-empty PostgreSQL password."""

        if not value.get_secret_value():
            raise ValueError("POSTGRES_PASSWORD must not be blank")
        return value

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, origins: list[str]) -> list[str]:
        """Accept explicit HTTP origins only; credentials and wildcards stay disabled."""

        normalized_origins: list[str] = []
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(f"invalid CORS origin: {origin!r}")
            normalized_origins.append(origin.rstrip("/"))
        return list(dict.fromkeys(normalized_origins))

    @model_validator(mode="after")
    def reject_debug_in_production(self) -> Self:
        """Prevent accidental debug responses in production."""

        if self.environment is AppEnvironment.PRODUCTION and self.debug:
            raise ValueError("debug must be disabled in production")
        if (
            self.environment in {AppEnvironment.STAGING, AppEnvironment.PRODUCTION}
            and self.postgres_password.get_secret_value() == "replace-this-local-password"
        ):
            raise ValueError("replace the local PostgreSQL password outside local/test")
        return self

    @property
    def database_url(self) -> PostgresDsn:
        """Build one async DSN from the canonical POSTGRES_* connection values."""

        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=quote(self.postgres_user, safe=""),
            password=quote(self.postgres_password.get_secret_value(), safe=""),
            host=self.postgres_host,
            port=self.postgres_port,
            path=quote(self.postgres_db, safe=""),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return one immutable settings instance per process."""

    return Settings()
