from __future__ import annotations

import logging
import secrets
from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger("wewin.config")


class Settings(BaseSettings):
    """Server configuration, read from WEWIN_* environment variables or a .env file."""

    model_config = SettingsConfigDict(env_prefix="WEWIN_", env_file=".env", extra="ignore")

    environment: Literal["development", "production"] = "development"

    host: str = "127.0.0.1"
    port: int = 8000

    database_url: str = "postgresql+psycopg://wewin:wewin@127.0.0.1:5433/wewin"
    secret_key: str = ""

    # Initial owner, created on first start when the database has no owner.
    organization_name: str = "WeWin"
    owner_email: str = "admin9531@gmail.com"
    owner_password: str = "asdqwe!@#123"
    owner_name: str = "Owner"

    access_token_minutes: int = 30
    refresh_token_hours: int = 12  # session length without "Remember me"
    remember_me_days: int = 30

    max_failed_logins: int = 5
    lockout_minutes: int = 15

    reset_code_minutes: int = 15
    reset_code_max_attempts: int = 5
    reset_code_resend_seconds: int = 60

    # Password-reset mail. Without smtp_host, codes are written to the server log.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "WeWin <no-reply@wewin.local>"
    smtp_starttls: bool = True

    @model_validator(mode="after")
    def _check_secret(self) -> Settings:
        if not self.secret_key:
            if self.environment == "production":
                raise ValueError("WEWIN_SECRET_KEY must be set in production")
            self.secret_key = secrets.token_urlsafe(64)
            log.warning("WEWIN_SECRET_KEY not set; using a temporary key (sessions end on restart)")
        elif len(self.secret_key) < 32:
            raise ValueError("WEWIN_SECRET_KEY must be at least 32 characters")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
