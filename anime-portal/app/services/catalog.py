"""Каталог аниме: выборки с фильтрацией/сортировкой и CRUD-правила целостности."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationAppError
from app.models.anime import Anime
from app.models.genre import Genre
from app.models.review import Review
from app.models.studio import Studio
from app.schemas.anime import ANIME_SORT_FIELDS, AnimeCreate, AnimeRead, AnimeUpdate


@dataclass(frozen=True)
class AnimeFilters:
    q: str | None = None
    genre: str | None = None
    studio_id: int | None = None
    year_from: int | None = None
    year_to: int | None = None
    status: str | None = None
    sort: str = "title"
    page: int = 1
    size: int = 20


def _rating_subquery() -> Any:
    return (
        select(
            Review.anime_id.label("anime_id"),
            func.avg(Review.rating).label("rating_avg"),
            func.count(Review.id).label("reviews_count"),
        )
        .group_by(Review.anime_id)
        .subquery()
    )


def _apply_filters(stmt: Any, filters: AnimeFilters) -> Any:
    conditions = []
    if filters.q:
        pattern = f"%{filters.q.strip().lower()}%"
        conditions.append(
            or_(
                func.lower(Anime.title).like(pattern),
                func.lower(func.coalesce(Anime.title_english, "")).like(pattern),
            )
        )
    if filters.genre:
        conditions.append(
            Anime.id.in_(
                select(Anime.id)
                .join(Anime.genres)
                .where(
                    or_(
                        func.lower(Genre.name) == filters.genre.lower(),
                        func.lower(Genre.slug) == filters.genre.lower(),
                    )
                )
            )
        )
    if filters.studio_id is not None:
        conditions.append(Anime.studio_id == filters.studio_id)
    if filters.year_from is not None:
        conditions.append(Anime.year >= filters.year_from)
    if filters.year_to is not None:
        conditions.append(Anime.year <= filters.year_to)
    if filters.status:
        conditions.append(Anime.status == filters.status)
    return stmt.where(and_(*conditions)) if conditions else stmt


def _order(stmt: Any, sort: str) -> Any:
    if sort not in ANIME_SORT_FIELDS:
        raise ValidationAppError(f"Недопустимое поле сортировки: {sort}")
    descending = sort.startswith("-")
    field = sort.lstrip("-")
    column = getattr(Anime, field)
    ordering = column.desc() if descending else column.asc()
    # Стабильный порядок при равных значениях — важно для пагинации.
    return stmt.order_by(ordering.nulls_last(), Anime.id.asc())


def _to_read(anime: Anime, rating_avg: float | None, reviews_count: int) -> AnimeRead:
    data = AnimeRead.model_validate(anime)
    return data.model_copy(
        update={
            "rating_avg": round(rating_avg, 2) if rating_avg is not None else None,
            "reviews_count": reviews_count,
        }
    )


def list_anime(session: Session, filters: AnimeFilters) -> tuple[list[AnimeRead], int]:
    ratings = _rating_subquery()
    base = select(Anime, ratings.c.rating_avg, ratings.c.reviews_count).outerjoin(
        ratings, ratings.c.anime_id == Anime.id
    )
    base = _apply_filters(base, filters)
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    stmt = _order(base, filters.sort).limit(filters.size).offset((filters.page - 1) * filters.size)
    rows = session.execute(stmt).unique().all()
    return [_to_read(anime, avg, count or 0) for anime, avg, count in rows], total


def get_anime(session: Session, anime_id: int) -> AnimeRead:
    ratings = _rating_subquery()
    row = session.execute(
        select(Anime, ratings.c.rating_avg, ratings.c.reviews_count)
        .outerjoin(ratings, ratings.c.anime_id == Anime.id)
        .where(Anime.id == anime_id)
    ).first()
    if row is None:
        raise NotFoundError(f"Аниме с id={anime_id} не найдено.")
    anime, avg, count = row
    return _to_read(anime, avg, count or 0)


def _require_anime(session: Session, anime_id: int) -> Anime:
    anime = session.get(Anime, anime_id)
    if anime is None:
        raise NotFoundError(f"Аниме с id={anime_id} не найдено.")
    return anime


def _resolve_studio(session: Session, studio_id: int | None) -> Studio | None:
    if studio_id is None:
        return None
    studio = session.get(Studio, studio_id)
    if studio is None:
        raise ValidationAppError(f"Студия с id={studio_id} не существует.")
    return studio


def _resolve_genres(session: Session, genre_ids: Sequence[int]) -> list[Genre]:
    unique_ids = list(dict.fromkeys(genre_ids))
    if not unique_ids:
        return []
    genres = list(session.scalars(select(Genre).where(Genre.id.in_(unique_ids))))
    if len(genres) != len(unique_ids):
        found = {genre.id for genre in genres}
        missing = [genre_id for genre_id in unique_ids if genre_id not in found]
        raise ValidationAppError(f"Жанры не найдены: {missing}")
    return genres


def create_anime(session: Session, payload: AnimeCreate) -> AnimeRead:
    if session.scalar(select(Anime.id).where(Anime.title == payload.title)):
        raise ConflictError(f"Аниме с названием «{payload.title}» уже существует.")
    anime = Anime(
        title=payload.title,
        title_english=payload.title_english,
        synopsis=payload.synopsis,
        year=payload.year,
        episodes=payload.episodes,
        status=payload.status,
        studio=_resolve_studio(session, payload.studio_id),
        genres=_resolve_genres(session, payload.genre_ids),
    )
    session.add(anime)
    session.commit()
    return get_anime(session, anime.id)


def update_anime(session: Session, anime_id: int, payload: AnimeUpdate) -> AnimeRead:
    anime = _require_anime(session, anime_id)
    data = payload.model_dump(exclude_unset=True)
    if "title" in data and data["title"] is not None:
        duplicate = session.scalar(
            select(Anime.id).where(Anime.title == data["title"], Anime.id != anime_id)
        )
        if duplicate:
            raise ConflictError(f"Аниме с названием «{data['title']}» уже существует.")
        anime.title = data["title"]
    if "studio_id" in data:
        anime.studio = _resolve_studio(session, data.pop("studio_id"))
    if "genre_ids" in data:
        genre_ids = data.pop("genre_ids") or []
        anime.genres = _resolve_genres(session, genre_ids)
    for field, value in data.items():
        if value is not None or field in {"title_english", "synopsis", "year", "episodes"}:
            setattr(anime, field, value)
    session.commit()
    return get_anime(session, anime_id)


def delete_anime(session: Session, anime_id: int) -> None:
    """Правило BR-4: тайтл с отзывами удалять нельзя — история оценок не теряется."""
    anime = _require_anime(session, anime_id)
    reviews = session.scalar(select(func.count(Review.id)).where(Review.anime_id == anime_id)) or 0
    if reviews:
        raise ConflictError(
            f"Нельзя удалить тайтл: у него {reviews} отзыв(ов). Сначала удалите отзывы."
        )
    session.delete(anime)
    session.commit()
