"""Настройки приложения: только из переменных окружения и .env, без секретов в коде."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Anime Portal"
    database_url: str = "sqlite:///./anime_portal.db"
    log_level: str = "INFO"
    page_size_default: int = Field(default=20, ge=1, le=100)
    page_size_max: int = Field(default=100, ge=1, le=500)

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
