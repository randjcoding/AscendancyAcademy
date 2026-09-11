"""Application settings from environment / .env."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    secret_key: str = "dev-insecure-secret-change-me"
    debug: bool = False
    port: int = 8030
    site_url: str = "http://127.0.0.1:8030"
    site_name: str = "Ascendancy Academy"

    database_url: str = "postgresql+psycopg://aa:change-me@localhost:5432/aa"

    teacher1_email: str = "joe@example.com"
    teacher1_password: str = "change-me-on-first-login"
    teacher1_first_name: str = "Joe"
    teacher1_last_name: str = "DiFede"

    teacher2_email: str = "kim@example.com"
    teacher2_password: str = "change-me-on-first-login"
    teacher2_first_name: str = "Kim"
    teacher2_last_name: str = "DiFede"

    student1_email: str = "gregory@example.com"
    student1_password: str = "change-me-on-first-login"
    student1_first_name: str = "Gregory"
    student1_last_name: str = "DiFede"

    cookie_secure: str = "auto"
    cookie_domain: str = ""
    session_cookie_name: str = "aa_session"
    session_ttl_hours: int = 720
    max_failed_attempts: int = 8
    lockout_minutes: int = 15

    turnstile_enabled: bool = False
    turnstile_site_key: str = ""
    turnstile_secret_key: str = ""
    turnstile_fail_open: bool = False

    storage_dir: str = "storage"
    testing: bool = False

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemma_base_url: str = ""
    gemma_relay_url: str = ""
    gemma_relay_secret: str = ""
    gemma_model: str = "gemma4:e4b"
    gemma_api_key: str = ""
    gemma_timeout_seconds: int = 180

    @property
    def storage_path(self) -> Path:
        path = Path(self.storage_dir)
        if not path.is_absolute():
            path = BASE_DIR / path
        return path

    def secure_cookie_for(self, request) -> bool:
        value = self.cookie_secure.strip().lower()
        if value in {"true", "1", "yes", "on"}:
            return True
        if value in {"false", "0", "no", "off"}:
            return False
        forwarded = request.headers.get("x-forwarded-proto", "")
        scheme = forwarded.split(",")[0].strip() or request.url.scheme
        return scheme.lower() == "https"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
