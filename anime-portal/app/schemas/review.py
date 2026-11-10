from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=10, examples=[9])
    body: str | None = Field(default=None, max_length=2000, examples=["Лучший тайм-луп."])


class ReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    anime_id: int
    user_id: int
    rating: int
    body: str | None
    created_at: datetime
