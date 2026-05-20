from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None


class TaskRef(BaseModel):
    id: UUID


class Timestamps(BaseModel):
    created_at: datetime
    updated_at: datetime | None = None
