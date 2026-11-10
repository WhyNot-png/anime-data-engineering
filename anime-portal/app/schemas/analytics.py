from pydantic import BaseModel


class TopAnimeItem(BaseModel):
    anime_id: int
    title: str
    year: int | None
    reviews_count: int
    rating_avg: float


class GenreStatItem(BaseModel):
    genre: str
    anime_count: int
    avg_rating: float | None


class YearStatItem(BaseModel):
    year: int
    titles: int
    episodes_total: int | None
