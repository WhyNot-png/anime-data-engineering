from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import AnimeStatus
from app.schemas.genre import GenreRead
from app.schemas.studio import StudioRead

Status = Literal["upcoming", "airing", "finished"]


class AnimeBase(BaseModel):
    title: str = Field(min_length=1, max_length=300, examples=["Steins;Gate"])
    title_english: str | None = Field(default=None, max_length=300, examples=["Steins;Gate"])
    synopsis: str | None = Field(default=None, max_length=4000)
    year: int | None = Field(default=None, ge=1900, le=2100, examples=[2011])
    episodes: int | None = Field(default=None, ge=0, le=10000, examples=[24])
    status: Status = "finished"
    studio_id: int | None = None
    genre_ids: list[int] = Field(default_factory=list, max_length=20)

    @field_validator("title", "title_english")
    @classmethod
    def strip_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Название не может быть пустым.")
        return stripped


class AnimeCreate(AnimeBase):
    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "Steins;Gate",
                "title_english": "Steins;Gate",
                "synopsis": "Учёный-любитель случайно изобретает способ отправлять сообщения в прошлое.",
                "year": 2011,
                "episodes": 24,
                "status": "finished",
                "studio_id": 1,
                "genre_ids": [1, 3],
            }
        }
    }


class AnimeUpdate(BaseModel):
    """Частичное обновление: любое переданное поле перезаписывается."""

    title: str | None = Field(default=None, min_length=1, max_length=300)
    title_english: str | None = Field(default=None, max_length=300)
    synopsis: str | None = Field(default=None, max_length=4000)
    year: int | None = Field(default=None, ge=1900, le=2100)
    episodes: int | None = Field(default=None, ge=0, le=10000)
    status: Status | None = None
    studio_id: int | None = None
    genre_ids: list[int] | None = Field(default=None, max_length=20)


class AnimeRead(AnimeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    studio: StudioRead | None = None
    genres: list[GenreRead] = Field(default_factory=list)
    rating_avg: float | None = Field(default=None, description="Средняя оценка по отзывам")
    reviews_count: int = Field(default=0)


class AnimeSort(str):
    pass


ANIME_SORT_FIELDS = (
    "title",
    "-title",
    "year",
    "-year",
    "episodes",
    "-episodes",
    "created_at",
    "-created_at",
)


def sort_field(value: str) -> str:
    if value not in ANIME_SORT_FIELDS:
        raise ValueError(f"Допустимые поля сортировки: {', '.join(ANIME_SORT_FIELDS)}")
    return value


__all__ = [
    "ANIME_SORT_FIELDS",
    "AnimeCreate",
    "AnimeRead",
    "AnimeUpdate",
    "AnimeStatus",
    "sort_field",
]
