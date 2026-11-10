from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.anime import Anime


class Studio(Base):
    __tablename__ = "studios"
    __table_args__ = (
        CheckConstraint(
            "founded_year IS NULL OR founded_year BETWEEN 1900 AND 2100",
            name="ck_studios_founded_year",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    founded_year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    anime: Mapped[list["Anime"]] = relationship(back_populates="studio")
