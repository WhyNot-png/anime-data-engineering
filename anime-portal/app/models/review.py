from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.anime import Anime
    from app.models.user import User


class Review(Base):
    """Отзыв: один на пару (пользователь, аниме), оценка 1–10."""

    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("user_id", "anime_id", name="uq_reviews_user_anime"),
        CheckConstraint("rating BETWEEN 1 AND 10", name="ck_reviews_rating"),
        CheckConstraint("length(body) <= 2000", name="ck_reviews_body_length"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    anime_id: Mapped[int] = mapped_column(
        ForeignKey("anime.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="reviews")
    anime: Mapped["Anime"] = relationship(back_populates="reviews")
