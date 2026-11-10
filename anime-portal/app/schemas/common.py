"""Общие схемы: страница пагинации и тело ошибки."""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int = Field(description="Всего записей, удовлетворяющих фильтру")
    page: int
    size: int
    pages: int


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: object | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail

    model_config = {
        "json_schema_extra": {
            "example": {
                "error": {
                    "code": "conflict",
                    "message": "Тайтл уже добавлен в список просмотра.",
                    "details": None,
                }
            }
        }
    }
