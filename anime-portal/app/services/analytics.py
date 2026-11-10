"""Аналитические агрегации: топ-N по оценкам, жанры, динамика по годам."""

from __future__ import annotations

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.models.anime import Anime, anime_genres
from app.models.genre import Genre
from app.models.review import Review
from app.schemas.analytics import GenreStatItem, TopAnimeItem, YearStatItem


def top_anime(session: Session, *, limit: int = 5, min_reviews: int = 1) -> list[TopAnimeItem]:
    """Топ по средней оценке среди тайтлов с достаточным числом отзывов."""
    stmt = (
        select(
            Anime.id,
            Anime.title,
            Anime.year,
            func.count(Review.id).label("reviews_count"),
            func.avg(Review.rating).label("rating_avg"),
        )
        .join(Review, Review.anime_id == Anime.id)
        .group_by(Anime.id, Anime.title, Anime.year)
        .having(func.count(Review.id) >= min_reviews)
        .order_by(func.avg(Review.rating).desc(), func.count(Review.id).desc(), Anime.id.asc())
        .limit(limit)
    )
    return [
        TopAnimeItem(
            anime_id=row.id,
            title=row.title,
            year=row.year,
            reviews_count=row.reviews_count,
            rating_avg=round(float(row.rating_avg), 2),
        )
        for row in session.execute(stmt)
    ]


def genre_stats(session: Session, *, limit: int = 10) -> list[GenreStatItem]:
    stmt = (
        select(
            Genre.name,
            func.count(func.distinct(Anime.id)).label("anime_count"),
            func.avg(Review.rating).label("avg_rating"),
        )
        .join(anime_genres, anime_genres.c.genre_id == Genre.id)
        .join(Anime, Anime.id == anime_genres.c.anime_id)
        .outerjoin(Review, Review.anime_id == Anime.id)
        .group_by(Genre.name)
        .order_by(func.count(func.distinct(Anime.id)).desc(), Genre.name.asc())
        .limit(limit)
    )
    return [
        GenreStatItem(
            genre=row.name,
            anime_count=row.anime_count,
            avg_rating=round(float(row.avg_rating), 2) if row.avg_rating is not None else None,
        )
        for row in session.execute(stmt)
    ]


def year_stats(
    session: Session, *, year_from: int | None = None, year_to: int | None = None
) -> list[YearStatItem]:
    """Динамика по годам: сколько тайтлов вышло и суммарное число эпизодов."""
    conditions: list[ColumnElement[bool]] = [Anime.year.is_not(None)]
    if year_from is not None:
        conditions.append(Anime.year >= year_from)
    if year_to is not None:
        conditions.append(Anime.year <= year_to)
    stmt = (
        select(Anime.year, func.count(Anime.id), func.sum(Anime.episodes))
        .where(*conditions)
        .group_by(Anime.year)
        .order_by(Anime.year.asc())
    )
    items: list[YearStatItem] = []
    for year, titles, episodes in session.execute(stmt):
        assert year is not None  # отфильтровано условием year IS NOT NULL
        items.append(
            YearStatItem(
                year=int(year),
                titles=int(titles),
                episodes_total=int(episodes) if episodes else None,
            )
        )
    return items
