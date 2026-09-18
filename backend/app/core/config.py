"""Typed application configuration loaded from environment variables."""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

# Local-only fallback so `uv run uvicorn` works with no .env editing. Rejected
# outright once APP_ENV=prod (see Settings.reject_debug_in_production).
LOCAL_JWT_SECRET = "local-development-only-change-me"


class Environment(StrEnum):
    LOCAL = "local"
    DEVELOPMENT = "dev"
    TEST = "test"
    PRODUCTION = "prod"


class Settings(BaseSettings):
    """Validated runtime settings."""

    model_config = SettingsConfigDict(
        env_file=(
            REPOSITORY_ROOT / "backend" / ".env",
            REPOSITORY_ROOT / "backend" / ".env.local",
        ),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="MacroRep API", alias="APP_NAME")
    app_env: Environment = Field(default=Environment.LOCAL, alias="APP_ENV")
    debug: bool = Field(default=False, alias="DEBUG")
    api_prefix: str = Field(default="/api", alias="API_PREFIX", pattern=r"^/[^\s]*$")
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"], alias="CORS_ORIGINS")
    preview_auth_enabled: bool = Field(default=True, alias="PREVIEW_AUTH_ENABLED")
    auto_create_schema: bool = Field(default=False, alias="AUTO_CREATE_SCHEMA")
    seed_demo_data: bool = Field(default=False, alias="SEED_DEMO_DATA")

    # Self-issued auth tokens (see app/auth). The secret only ever signs our own
    # access tokens; rotate it in production.
    jwt_secret_key: str = Field(default=LOCAL_JWT_SECRET, alias="JWT_SECRET_KEY", min_length=1)
    access_token_ttl_minutes: int = Field(default=15, alias="ACCESS_TOKEN_TTL_MINUTES", ge=1)
    refresh_token_ttl_days: int = Field(default=30, alias="REFRESH_TOKEN_TTL_DAYS", ge=1)

    # The refresh token travels as an httpOnly cookie rather than in a response
    # body, so a script injected into the page cannot read it. The path is
    # narrowed to the auth routes to keep it off every other request, and
    # SameSite is the CSRF defence a bearer token never needed.
    #
    # The default path matches where `app.auth.router` mounts, which is fixed at
    # `/api` regardless of API_PREFIX. A frontend on a different origin needs
    # `none` here, plus `secure`, plus CSRF tokens of its own.
    refresh_cookie_name: str = Field(
        default="macrorep_refresh", alias="REFRESH_COOKIE_NAME", min_length=1
    )
    refresh_cookie_path: str = Field(
        default="/api/auth", alias="REFRESH_COOKIE_PATH", pattern=r"^/[^\s]*$"
    )
    refresh_cookie_domain: str | None = Field(default=None, alias="REFRESH_COOKIE_DOMAIN")
    refresh_cookie_secure: bool = Field(default=False, alias="REFRESH_COOKIE_SECURE")
    refresh_cookie_samesite: Literal["lax", "strict", "none"] = Field(
        default="strict", alias="REFRESH_COOKIE_SAMESITE"
    )

    database_url: str = Field(alias="DATABASE_URL", min_length=1)
    database_echo: bool = Field(default=False, alias="DATABASE_ECHO")
    database_pool_size: int = Field(default=10, alias="DATABASE_POOL_SIZE", ge=1, le=100)
    database_max_overflow: int = Field(default=20, alias="DATABASE_MAX_OVERFLOW", ge=0, le=200)

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_json: bool = Field(default=True, alias="LOG_JSON")
    correlation_id_header: str = Field(
        default="X-Correlation-ID", alias="CORRELATION_ID_HEADER", min_length=1
    )

    @field_validator("jwt_secret_key", mode="before")
    @classmethod
    def blank_secret_falls_back_to_local(cls, value: object) -> object:
        """`JWT_SECRET_KEY=` with nothing after it means "leave this unset".

        `.env.example` ships the key blank as a prompt; without this, copying it
        to `.env` would fail the `min_length` check instead of staying local.
        """

        return LOCAL_JWT_SECRET if value == "" else value

    @model_validator(mode="after")
    def reject_debug_in_production(self) -> Settings:
        if self.app_env is Environment.PRODUCTION and self.debug:
            raise ValueError("DEBUG must be false in production")
        if self.app_env is Environment.PRODUCTION and self.preview_auth_enabled:
            raise ValueError("PREVIEW_AUTH_ENABLED must be false in production")
        if self.app_env is Environment.PRODUCTION and self.auto_create_schema:
            raise ValueError("AUTO_CREATE_SCHEMA must be false in production; use Alembic")
        if self.app_env is Environment.PRODUCTION and self.seed_demo_data:
            raise ValueError("SEED_DEMO_DATA must be false in production")
        if self.app_env is Environment.PRODUCTION and self.jwt_secret_key == LOCAL_JWT_SECRET:
            raise ValueError("JWT_SECRET_KEY must be set to a private value in production")
        if self.app_env is Environment.PRODUCTION and not self.refresh_cookie_secure:
            raise ValueError("REFRESH_COOKIE_SECURE must be true in production")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide immutable-in-practice settings instance."""

    return Settings()


def clear_settings_cache() -> None:
    """Clear cached settings; intended for tests that change the environment."""

    get_settings.cache_clear()
