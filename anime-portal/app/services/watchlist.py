"""Список просмотра: правила статусов и прогресса (BR-1, BR-2, BR-3)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationAppError
from app.models.anime import Anime
from app.models.enums import WatchStatus
from app.models.user import User
from app.models.watch import WatchEntry
from app.schemas.watch import WatchEntryCreate, WatchEntryUpdate


def _require_user(session: Session, user_id: int) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise NotFoundError(f"Пользователь с id={user_id} не найден.")
    return user


def _require_entry(session: Session, entry_id: int) -> WatchEntry:
    entry = session.get(WatchEntry, entry_id)
    if entry is None:
        raise NotFoundError(f"Запись списка просмотра с id={entry_id} не найдена.")
    return entry


def _episode_limit(anime: Anime) -> int | None:
    """None означает «число эпизодов неизвестно» — верхней границы прогресса нет."""
    return anime.episodes if anime.episodes else None


def _validate_progress(anime: Anime, progress: int) -> None:
    limit = _episode_limit(anime)
    if limit is not None and progress > limit:
        raise ConflictError(
            f"Прогресс {progress} превышает число эпизодов ({limit}) у «{anime.title}»."
        )


def _resolve_status(anime: Anime, status: str, progress: int) -> str:
    """BR-2: completed ⟺ просмотрены все эпизоды; watching требует прогресса ≥ 1."""
    limit = _episode_limit(anime)
    if status == WatchStatus.COMPLETED and limit is not None and progress < limit:
        raise ConflictError(
            f"Нельзя завершить «{anime.title}»: просмотрено {progress} из {limit} эпизодов."
        )
    if status == WatchStatus.WATCHING and progress == 0:
        raise ValidationAppError("Статус watching требует прогресса хотя бы в 1 эпизод.")
    if status == WatchStatus.PLANNED and progress > 0:
        # Начатый просмотр не может оставаться в статусе «запланировано».
        status = WatchStatus.WATCHING.value
    if limit is not None and progress == limit and status != WatchStatus.DROPPED:
        return WatchStatus.COMPLETED.value
    return status


def add_entry(session: Session, user_id: int, payload: WatchEntryCreate) -> WatchEntry:
    """BR-1: одна запись на пару (пользователь, аниме)."""
    _require_user(session, user_id)
    anime = session.get(Anime, payload.anime_id)
    if anime is None:
        raise NotFoundError(f"Аниме с id={payload.anime_id} не найдено.")
    exists = session.scalar(
        select(WatchEntry.id).where(
            WatchEntry.user_id == user_id, WatchEntry.anime_id == payload.anime_id
        )
    )
    if exists:
        raise ConflictError("Этот тайтл уже добавлен в список просмотра.")
    _validate_progress(anime, payload.progress)
    status = _resolve_status(anime, payload.status, payload.progress)
    entry = WatchEntry(user_id=user_id, anime_id=anime.id, status=status, progress=payload.progress)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def list_entries(
    session: Session, user_id: int, *, status: str | None = None, page: int = 1, size: int = 20
) -> tuple[list[WatchEntry], int]:
    _require_user(session, user_id)
    conditions = [WatchEntry.user_id == user_id]
    if status:
        conditions.append(WatchEntry.status == status)
    total = session.scalar(select(func.count(WatchEntry.id)).where(*conditions)) or 0
    entries = list(
        session.scalars(
            select(WatchEntry)
            .where(*conditions)
            .order_by(WatchEntry.updated_at.desc(), WatchEntry.id.desc())
            .limit(size)
            .offset((page - 1) * size)
        )
    )
    return entries, total


def update_entry(session: Session, entry_id: int, payload: WatchEntryUpdate) -> WatchEntry:
    entry = _require_entry(session, entry_id)
    anime = entry.anime
    progress = payload.progress if payload.progress is not None else entry.progress
    status = payload.status if payload.status is not None else entry.status
    if payload.status is None and payload.progress is None:
        raise ValidationAppError("Укажите status или progress.")
    _validate_progress(anime, progress)
    entry.progress = progress
    entry.status = _resolve_status(anime, status, progress)
    session.commit()
    session.refresh(entry)
    return entry


def delete_entry(session: Session, entry_id: int) -> None:
    entry = _require_entry(session, entry_id)
    session.delete(entry)
    session.commit()


def get_entry(session: Session, entry_id: int) -> WatchEntry:
    return _require_entry(session, entry_id)


def require_completed(session: Session, user_id: int, anime_id: int) -> WatchEntry:
    """BR-3: отзыв доступен только после полного просмотра."""
    entry = session.scalar(
        select(WatchEntry).where(WatchEntry.user_id == user_id, WatchEntry.anime_id == anime_id)
    )
    if entry is None:
        raise ConflictError("Сначала добавьте тайтл в список просмотра.")
    if entry.status != WatchStatus.COMPLETED:
        raise ConflictError("Отзыв можно оставить только после полного просмотра (completed).")
    return entry
