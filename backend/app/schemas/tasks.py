from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import TaskStatus, TaskType


class TaskRead(BaseModel):
    id: UUID
    file_id: UUID | None
    page_id: UUID | None
    type: TaskType
    status: TaskStatus
    input_payload: dict
    output_payload: dict | None
    error_message: str | None
    attempts: int
    max_attempts: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
