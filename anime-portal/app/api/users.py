"""Пользователи, их списки просмотра и отзывы."""

from typing import Annotated

from fastapi import APIRouter, Path, Query, Response, status
from sqlalchemy import func, select

from app.api.deps import PaginationDep, SessionDep, pages
from app.core.errors import ConflictError, NotFoundError
from app.models.user import User
from app.schemas.common import ErrorResponse, Page
from app.schemas.review import ReviewCreate, ReviewRead
from app.schemas.user import UserCreate, UserRead
from app.schemas.watch import WatchEntryCreate, WatchEntryRead, WatchEntryUpdate
from app.services import reviews, watchlist

router = APIRouter(tags=["users"])
UserId = Annotated[int, Path(ge=1)]


@router.get("/users", response_model=Page[UserRead], summary="Список пользователей")
def list_users(session: SessionDep, pagination: PaginationDep) -> Page[UserRead]:
    total = session.scalar(select(func.count(User.id))) or 0
    rows = session.scalars(
        select(User).order_by(User.id.asc()).limit(pagination.size).offset(pagination.offset)
    )
    return Page(
        items=[UserRead.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        size=pagination.size,
        pages=pages(total, pagination.size),
    )


@router.post(
    "/users",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать пользователя",
    responses={409: {"model": ErrorResponse}},
)
def create_user(payload: UserCreate, session: SessionDep) -> UserRead:
    email = str(payload.email).lower()
    if session.scalar(select(User.id).where(User.email == email)):
        raise ConflictError("Пользователь с таким email уже существует.")
    if session.scalar(select(User.id).where(User.username == payload.username)):
        raise ConflictError("Такое имя пользователя занято.")
    user = User(email=email, username=payload.username)
    session.add(user)
    session.commit()
    session.refresh(user)
    return UserRead.model_validate(user)


@router.get(
    "/users/{user_id}",
    response_model=UserRead,
    summary="Получить пользователя",
    responses={404: {"model": ErrorResponse}},
)
def get_user(user_id: UserId, session: SessionDep) -> UserRead:
    user = session.get(User, user_id)
    if user is None:
        raise NotFoundError(f"Пользователь с id={user_id} не найден.")
    return UserRead.model_validate(user)


@router.get(
    "/users/{user_id}/watchlist",
    response_model=Page[WatchEntryRead],
    summary="Список просмотра пользователя",
    responses={404: {"model": ErrorResponse}},
)
def list_watchlist(
    user_id: UserId,
    session: SessionDep,
    pagination: PaginationDep,
    status_filter: Annotated[
        str | None, Query(alias="status", description="planned/watching/completed/dropped")
    ] = None,
) -> Page[WatchEntryRead]:
    entries, total = watchlist.list_entries(
        session, user_id, status=status_filter, page=pagination.page, size=pagination.size
    )
    return Page(
        items=[WatchEntryRead.model_validate(entry) for entry in entries],
        total=total,
        page=pagination.page,
        size=pagination.size,
        pages=pages(total, pagination.size),
    )


@router.post(
    "/users/{user_id}/watchlist",
    response_model=WatchEntryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить тайтл в список просмотра",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def add_watch_entry(
    user_id: UserId, payload: WatchEntryCreate, session: SessionDep
) -> WatchEntryRead:
    return WatchEntryRead.model_validate(watchlist.add_entry(session, user_id, payload))


@router.patch(
    "/watchlist/{entry_id}",
    response_model=WatchEntryRead,
    summary="Обновить прогресс/статус (автозавершение при достижении конца)",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def update_watch_entry(
    entry_id: Annotated[int, Path(ge=1)], payload: WatchEntryUpdate, session: SessionDep
) -> WatchEntryRead:
    return WatchEntryRead.model_validate(watchlist.update_entry(session, entry_id, payload))


@router.delete(
    "/watchlist/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить запись из списка просмотра",
    responses={404: {"model": ErrorResponse}},
)
def delete_watch_entry(entry_id: Annotated[int, Path(ge=1)], session: SessionDep) -> Response:
    watchlist.delete_entry(session, entry_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/anime/{anime_id}/reviews",
    response_model=Page[ReviewRead],
    summary="Отзывы по тайтлу",
    responses={404: {"model": ErrorResponse}},
)
def list_reviews(
    anime_id: Annotated[int, Path(ge=1)],
    session: SessionDep,
    pagination: PaginationDep,
) -> Page[ReviewRead]:
    items, total = reviews.list_reviews(
        session, anime_id, page=pagination.page, size=pagination.size
    )
    return Page(
        items=[ReviewRead.model_validate(review) for review in items],
        total=total,
        page=pagination.page,
        size=pagination.size,
        pages=pages(total, pagination.size),
    )


@router.post(
    "/anime/{anime_id}/reviews",
    response_model=ReviewRead,
    status_code=status.HTTP_201_CREATED,
    summary="Оставить отзыв (только после completed)",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def create_review(
    anime_id: Annotated[int, Path(ge=1)],
    payload: ReviewCreate,
    session: SessionDep,
    user_id: Annotated[int, Query(ge=1, description="Автор отзыва")],
) -> ReviewRead:
    review = reviews.create_review(session, user_id, anime_id, payload)
    return ReviewRead.model_validate(review)


@router.delete(
    "/reviews/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить отзыв",
    responses={404: {"model": ErrorResponse}},
)
def delete_review(review_id: Annotated[int, Path(ge=1)], session: SessionDep) -> Response:
    reviews.delete_review(session, review_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
