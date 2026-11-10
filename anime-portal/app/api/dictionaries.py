"""Справочники: студии и жанры."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import PaginationDep, SessionDep, pages
from app.core.errors import ConflictError, NotFoundError
from app.models.anime import Anime
from app.models.genre import Genre
from app.models.studio import Studio
from app.schemas.common import ErrorResponse, Page
from app.schemas.genre import GenreCreate, GenreRead
from app.schemas.studio import StudioCreate, StudioRead

studios_router = APIRouter(prefix="/studios", tags=["studios"])
genres_router = APIRouter(prefix="/genres", tags=["genres"])


@studios_router.get("", response_model=Page[StudioRead], summary="Список студий")
def list_studios(session: SessionDep, pagination: PaginationDep) -> Page[StudioRead]:
    total = session.scalar(select(func.count(Studio.id))) or 0
    rows = session.scalars(
        select(Studio).order_by(Studio.name.asc()).limit(pagination.size).offset(pagination.offset)
    )
    return Page(
        items=[StudioRead.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        size=pagination.size,
        pages=pages(total, pagination.size),
    )


@studios_router.post(
    "",
    response_model=StudioRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать студию",
    responses={409: {"model": ErrorResponse}},
)
def create_studio(payload: StudioCreate, session: SessionDep) -> StudioRead:
    if session.scalar(select(Studio.id).where(Studio.name == payload.name)):
        raise ConflictError(f"Студия «{payload.name}» уже существует.")
    studio = Studio(**payload.model_dump())
    session.add(studio)
    session.commit()
    session.refresh(studio)
    return StudioRead.model_validate(studio)


@studios_router.delete(
    "/{studio_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить студию без тайтлов",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def delete_studio(studio_id: int, session: SessionDep) -> None:
    studio = session.get(Studio, studio_id)
    if studio is None:
        raise NotFoundError(f"Студия с id={studio_id} не найдена.")
    linked = session.scalar(select(func.count(Anime.id)).where(Anime.studio_id == studio_id)) or 0
    if linked:
        raise ConflictError(f"Нельзя удалить студию: к ней привязано {linked} тайтл(ов).")
    session.delete(studio)
    session.commit()


@genres_router.get("", response_model=list[GenreRead], summary="Список жанров")
def list_genres(session: SessionDep) -> list[GenreRead]:
    rows = session.scalars(select(Genre).order_by(Genre.name.asc()))
    return [GenreRead.model_validate(row) for row in rows]


@genres_router.post(
    "",
    response_model=GenreRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать жанр",
    responses={409: {"model": ErrorResponse}},
)
def create_genre(payload: GenreCreate, session: SessionDep) -> GenreRead:
    slug = (payload.slug or payload.name).strip().lower().replace(" ", "-")
    if session.scalar(select(Genre.id).where(Genre.name == payload.name)):
        raise ConflictError(f"Жанр «{payload.name}» уже существует.")
    genre = Genre(name=payload.name, slug=slug)
    session.add(genre)
    session.commit()
    session.refresh(genre)
    return GenreRead.model_validate(genre)


__all__ = ["genres_router", "studios_router", "Depends", "Query", "Annotated", "Session"]
