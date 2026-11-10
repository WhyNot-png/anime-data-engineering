from pydantic import BaseModel, ConfigDict, Field


class GenreCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80, examples=["Sci-Fi"])
    slug: str | None = Field(default=None, max_length=80, description="По умолчанию из name")


class GenreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
