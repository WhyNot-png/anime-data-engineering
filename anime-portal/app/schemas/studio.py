from pydantic import BaseModel, ConfigDict, Field


class StudioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200, examples=["Kyoto Animation"])
    country: str | None = Field(default=None, max_length=100, examples=["Japan"])
    founded_year: int | None = Field(default=None, ge=1900, le=2100, examples=[1981])


class StudioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    country: str | None
    founded_year: int | None
