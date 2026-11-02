from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Application settings, loaded from backend/.env."""

    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Comma-separated list of browser origins allowed to call the API.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # The refresh token travels in an httpOnly cookie. Behind HTTPS set
    # COOKIE_SECURE=true. If the frontend and API live on different *sites*
    # (e.g. app.example.com vs api.other.com) the cookie is cross-site and needs
    # COOKIE_SAMESITE=none (which browsers only accept together with Secure).
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"

    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    @model_validator(mode="after")
    def _samesite_none_requires_secure(self):
        if self.cookie_samesite == "none" and not self.cookie_secure:
            raise ValueError("COOKIE_SAMESITE=none requires COOKIE_SECURE=true")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
