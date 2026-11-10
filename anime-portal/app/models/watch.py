from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import WATCH_STATUS_VALUES

if TYPE_CHECKING:
    from app.models.anime import Anime
    from app.models.user import User

_status_list = ", ".join(f"'{value}'" for value in WATCH_STATUS_VALUES)


class WatchEntry(Base):
    """Строка списка просмотра: одна запись на пару (пользователь, аниме)."""

    __tablename__ = "watch_entries"
    __table_args__ = (
        UniqueConstraint("user_id", "anime_id", name="uq_watch_entries_user_anime"),
        CheckConstraint(f"status IN ({_status_list})", name="ck_watch_entries_status"),
        CheckConstraint("progress >= 0", name="ck_watch_entries_progress"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    anime_id: Mapped[int] = mapped_column(
        ForeignKey("anime.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="watch_entries")
    anime: Mapped["Anime"] = relationship(back_populates="watch_entries", lazy="joined")
