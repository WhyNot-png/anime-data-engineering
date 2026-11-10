"""Аналитические эндпоинты: агрегации по отзывам, жанрам и годам."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import SessionDep
from app.schemas.analytics import GenreStatItem, TopAnimeItem, YearStatItem
from app.services import analytics

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get(
    "/top-anime",
    response_model=list[TopAnimeItem],
    summary="Топ-N тайтлов по средней оценке",
    description="Учитываются тайтлы с числом отзывов не меньше min_reviews.",
)
def top_anime(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 5,
    min_reviews: Annotated[int, Query(ge=1, le=100)] = 1,
) -> list[TopAnimeItem]:
    return analytics.top_anime(session, limit=limit, min_reviews=min_reviews)


@router.get(
    "/genres",
    response_model=list[GenreStatItem],
    summary="Популярность жанров и средняя оценка",
)
def genre_stats(
    session: SessionDep, limit: Annotated[int, Query(ge=1, le=50)] = 10
) -> list[GenreStatItem]:
    return analytics.genre_stats(session, limit=limit)


@router.get(
    "/years",
    response_model=list[YearStatItem],
    summary="Динамика по годам: число тайтлов и суммарные эпизоды",
)
def year_stats(
    session: SessionDep,
    year_from: Annotated[int | None, Query(ge=1900, le=2100)] = None,
    year_to: Annotated[int | None, Query(ge=1900, le=2100)] = None,
) -> list[YearStatItem]:
    return analytics.year_stats(session, year_from=year_from, year_to=year_to)
