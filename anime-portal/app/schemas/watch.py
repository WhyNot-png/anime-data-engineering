from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.anime import AnimeRead

WatchStatusLiteral = Literal["planned", "watching", "completed", "dropped"]


class WatchEntryCreate(BaseModel):
    anime_id: int
    status: WatchStatusLiteral = "planned"
    progress: int = Field(default=0, ge=0)


class WatchEntryUpdate(BaseModel):
    """Прогресс и статус меняются вместе: правило автозавершения живёт в сервисе."""

    status: WatchStatusLiteral | None = None
    progress: int | None = Field(default=None, ge=0)


class WatchEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    progress: int
    created_at: datetime
    updated_at: datetime
    anime: AnimeRead
