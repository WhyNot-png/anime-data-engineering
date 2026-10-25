from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Task, User
from app.schemas import TaskCreate, TaskRead, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])


async def require_owner(session: AsyncSession, owner_id: int) -> None:
    if await session.get(User, owner_id) is None:
        raise HTTPException(404, "Owner not found")


async def require_task(session: AsyncSession, task_id: int) -> Task:
    task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(404, "Task not found")
    return task


@router.post(
    "",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
    responses={404: {"description": "Owner not found"}},
)
async def create_task(payload: TaskCreate, session: AsyncSession = Depends(get_session)) -> Task:
    await require_owner(session, payload.owner_id)
    task = Task(**payload.model_dump())
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


@router.get("", response_model=list[TaskRead])
async def list_tasks(
    done: bool | None = None,
    owner_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[Task]:
    query = select(Task).order_by(Task.id)
    if done is not None:
        query = query.where(Task.done == done)
    if owner_id is not None:
        query = query.where(Task.owner_id == owner_id)
    result = await session.scalars(query.offset(offset).limit(limit))
    return list(result)


@router.get("/{id}", response_model=TaskRead, responses={404: {"description": "Task not found"}})
async def get_task(id: int = Path(gt=0), session: AsyncSession = Depends(get_session)) -> Task:
    return await require_task(session, id)


@router.patch(
    "/{id}", response_model=TaskRead, responses={404: {"description": "Task or owner not found"}}
)
async def update_task(
    payload: TaskUpdate, id: int = Path(gt=0), session: AsyncSession = Depends(get_session)
) -> Task:
    task = await require_task(session, id)
    updates = payload.model_dump(exclude_unset=True)
    if "owner_id" in updates:
        await require_owner(session, updates["owner_id"])
    for field, value in updates.items():
        setattr(task, field, value)
    await session.commit()
    await session.refresh(task)
    return task


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={404: {"description": "Task not found"}},
)
async def delete_task(
    id: int = Path(gt=0), session: AsyncSession = Depends(get_session)
) -> Response:
    task = await require_task(session, id)
    await session.delete(task)
    await session.commit()
    return Response(status_code=204)
