from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import User
from app.schemas import UserCreate, UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"description": "Email already registered"}},
)
async def create_user(payload: UserCreate, session: AsyncSession = Depends(get_session)) -> User:
    user = User(**payload.model_dump())
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        if getattr(exc.orig, "sqlstate", None) == "23505":
            raise HTTPException(409, "Email already registered") from None
        raise
    await session.refresh(user)
    return user


@router.get("/{id}", response_model=UserRead, responses={404: {"description": "User not found"}})
async def get_user(id: int = Path(gt=0), session: AsyncSession = Depends(get_session)) -> User:
    user = await session.get(User, id)
    if user is None:
        raise HTTPException(404, "User not found")
    return user
