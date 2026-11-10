from typing import Annotated

from fastapi import APIRouter, Path, Query, Response, status

from app.api.deps import PaginationDep, SessionDep, pages
from app.models.enums import ANIME_STATUS_VALUES
from app.schemas.anime import AnimeCreate, AnimeRead, AnimeUpdate
from app.schemas.common import ErrorResponse, Page
from app.services import catalog

router = APIRouter(prefix="/anime", tags=["anime"])

AnimeId = Annotated[int, Path(ge=1, description="Идентификатор тайтла")]


@router.get(
    "",
    response_model=Page[AnimeRead],
    summary="Список аниме с фильтрацией, сортировкой и пагинацией",
    responses={422: {"model": ErrorResponse}},
)
def list_anime(
    session: SessionDep,
    pagination: PaginationDep,
    q: Annotated[str | None, Query(max_length=200, description="Поиск по названию")] = None,
    genre: Annotated[str | None, Query(description="Жанр: имя или slug")] = None,
    studio_id: Annotated[int | None, Query(ge=1)] = None,
    year_from: Annotated[int | None, Query(ge=1900, le=2100)] = None,
    year_to: Annotated[int | None, Query(ge=1900, le=2100)] = None,
    status_filter: Annotated[
        str | None,
        Query(alias="status", description=f"Одно из: {', '.join(ANIME_STATUS_VALUES)}"),
    ] = None,
    sort: Annotated[str, Query(description="Например: title, -year, episodes")] = "title",
) -> Page[AnimeRead]:
    filters = catalog.AnimeFilters(
        q=q,
        genre=genre,
        studio_id=studio_id,
        year_from=year_from,
        year_to=year_to,
        status=status_filter,
        sort=sort,
        page=pagination.page,
        size=pagination.size,
    )
    items, total = catalog.list_anime(session, filters)
    return Page(
        items=items,
        total=total,
        page=pagination.page,
        size=pagination.size,
        pages=pages(total, pagination.size),
    )


@router.post(
    "",
    response_model=AnimeRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать тайтл",
    responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def create_anime(payload: AnimeCreate, session: SessionDep) -> AnimeRead:
    return catalog.create_anime(session, payload)


@router.get(
    "/{anime_id}",
    response_model=AnimeRead,
    summary="Получить тайтл по id",
    responses={404: {"model": ErrorResponse}},
)
def get_anime(anime_id: AnimeId, session: SessionDep) -> AnimeRead:
    return catalog.get_anime(session, anime_id)


@router.patch(
    "/{anime_id}",
    response_model=AnimeRead,
    summary="Частично обновить тайтл",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def update_anime(anime_id: AnimeId, payload: AnimeUpdate, session: SessionDep) -> AnimeRead:
    return catalog.update_anime(session, anime_id, payload)


@router.delete(
    "/{anime_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить тайтл (запрещено при наличии отзывов)",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def delete_anime(anime_id: AnimeId, session: SessionDep) -> Response:
    catalog.delete_anime(session, anime_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
