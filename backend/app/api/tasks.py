from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.enums import TaskStatus, TaskType
from app.models.task import Task
from app.schemas.tasks import TaskRead

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskRead])
async def list_tasks(
    file_id: UUID | None = Query(default=None),
    status: TaskStatus | None = Query(default=None),
    type: TaskType | None = Query(default=None),  # noqa: A002
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[TaskRead]:
    query = select(Task).order_by(Task.created_at.desc()).limit(limit).offset(offset)
    if file_id:
        query = query.where(Task.file_id == file_id)
    if status:
        query = query.where(Task.status == status)
    if type:
        query = query.where(Task.type == type)
    items = (await db.execute(query)).scalars().all()
    return [TaskRead.model_validate(it, from_attributes=True) for it in items]


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(task_id: UUID, db: AsyncSession = Depends(get_db)) -> TaskRead:
    model = await db.get(Task, task_id)
    if not model:
        raise HTTPException(status_code=404, detail="task not found")
    return TaskRead.model_validate(model, from_attributes=True)
