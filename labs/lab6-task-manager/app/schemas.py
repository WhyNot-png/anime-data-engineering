from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UserCreate(InputModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=200)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    name: str
    created_at: datetime


class UserUpdate(InputModel):
    email: EmailStr | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("email", "name", mode="before")
    @classmethod
    def reject_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("This field cannot be null")
        return value


class TaskCreate(InputModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    done: bool = False
    owner_id: int = Field(gt=0)


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: str | None
    done: bool
    created_at: datetime
    owner_id: int


class TaskUpdate(InputModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    done: bool | None = None
    owner_id: int | None = Field(default=None, gt=0)

    @field_validator("title", "done", "owner_id", mode="before")
    @classmethod
    def reject_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("This field cannot be null")
        return value
