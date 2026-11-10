"""Общие зависимости FastAPI: сессия БД и пагинация."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ValidationAppError
from app.db import get_session

SessionDep = Annotated[Session, Depends(get_session)]


@dataclass(frozen=True)
class Pagination:
    page: int
    size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


def pagination(
    page: Annotated[int, Query(ge=1, description="Номер страницы, начиная с 1")] = 1,
    size: Annotated[int | None, Query(ge=1, description="Размер страницы")] = None,
) -> Pagination:
    settings = get_settings()
    resolved = size or settings.page_size_default
    if resolved > settings.page_size_max:
        raise ValidationAppError(f"Размер страницы не может превышать {settings.page_size_max}.")
    return Pagination(page=page, size=resolved)


PaginationDep = Annotated[Pagination, Depends(pagination)]


def pages(total: int, size: int) -> int:
    return (total + size - 1) // size if size else 0
