from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import ANIME_STATUS_VALUES

if TYPE_CHECKING:
    from app.models.genre import Genre
    from app.models.review import Review
    from app.models.studio import Studio
    from app.models.watch import WatchEntry

_status_list = ", ".join(f"'{value}'" for value in ANIME_STATUS_VALUES)

anime_genres = Table(
    "anime_genres",
    Base.metadata,
    Column("anime_id", ForeignKey("anime.id", ondelete="CASCADE"), primary_key=True),
    Column("genre_id", ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True, index=True),
)


class Anime(Base):
    __tablename__ = "anime"
    __table_args__ = (
        CheckConstraint(f"status IN ({_status_list})", name="ck_anime_status"),
        CheckConstraint("episodes IS NULL OR episodes >= 0", name="ck_anime_episodes"),
        CheckConstraint("year IS NULL OR year BETWEEN 1900 AND 2100", name="ck_anime_year"),
        CheckConstraint("length(title) BETWEEN 1 AND 300", name="ck_anime_title_length"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    mal_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    title_english: Mapped[str | None] = mapped_column(String(300), nullable=True)
    synopsis: Mapped[str | None] = mapped_column(Text, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    episodes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="finished", index=True)
    studio_id: Mapped[int | None] = mapped_column(
        ForeignKey("studios.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    studio: Mapped["Studio | None"] = relationship(back_populates="anime", lazy="joined")
    genres: Mapped[list["Genre"]] = relationship(
        secondary=anime_genres, back_populates="anime", lazy="selectin", order_by="Genre.name"
    )
    reviews: Mapped[list["Review"]] = relationship(
        back_populates="anime", cascade="all, delete-orphan", passive_deletes=True
    )
    watch_entries: Mapped[list["WatchEntry"]] = relationship(
        back_populates="anime", cascade="all, delete-orphan", passive_deletes=True
    )
