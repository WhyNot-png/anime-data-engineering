"""Отзывы и оценки: BR-3 (только после completed) и один отзыв на тайтл."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models.anime import Anime
from app.models.review import Review
from app.models.user import User
from app.schemas.review import ReviewCreate
from app.services.watchlist import require_completed


def create_review(session: Session, user_id: int, anime_id: int, payload: ReviewCreate) -> Review:
    if session.get(User, user_id) is None:
        raise NotFoundError(f"Пользователь с id={user_id} не найден.")
    if session.get(Anime, anime_id) is None:
        raise NotFoundError(f"Аниме с id={anime_id} не найдено.")
    require_completed(session, user_id, anime_id)
    duplicate = session.scalar(
        select(Review.id).where(Review.user_id == user_id, Review.anime_id == anime_id)
    )
    if duplicate:
        raise ConflictError("Вы уже оставили отзыв на этот тайтл.")
    review = Review(user_id=user_id, anime_id=anime_id, rating=payload.rating, body=payload.body)
    session.add(review)
    session.commit()
    session.refresh(review)
    return review


def list_reviews(
    session: Session, anime_id: int, *, page: int = 1, size: int = 20
) -> tuple[list[Review], int]:
    if session.get(Anime, anime_id) is None:
        raise NotFoundError(f"Аниме с id={anime_id} не найдено.")
    total = session.scalar(select(func.count(Review.id)).where(Review.anime_id == anime_id)) or 0
    reviews = list(
        session.scalars(
            select(Review)
            .where(Review.anime_id == anime_id)
            .order_by(Review.created_at.desc(), Review.id.desc())
            .limit(size)
            .offset((page - 1) * size)
        )
    )
    return reviews, total


def delete_review(session: Session, review_id: int) -> None:
    review = session.get(Review, review_id)
    if review is None:
        raise NotFoundError(f"Отзыв с id={review_id} не найден.")
    session.delete(review)
    session.commit()
