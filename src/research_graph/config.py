"""Validated settings loaded from RG_* variables and an optional .env file."""

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RG_", env_file=".env", extra="ignore")

    github_token: str | None = Field(default=None, repr=False)
    data_dir: Path = Path("data")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["text", "json"] = "text"
    request_timeout: float = Field(default=30.0, gt=0, le=300, allow_inf_nan=False)
    max_concurrency: int = Field(default=8, ge=1, le=64)

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    def ensure_data_dir(self) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir


def get_settings() -> Settings:
    """Read settings on every call; do not cache environment-dependent state."""
    return Settings()
