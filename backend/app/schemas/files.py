from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import FileStatus, PageStatus


class FileRead(BaseModel):
    id: UUID
    filename: str
    content_type: str
    size_bytes: int
    status: FileStatus
    pages_count: int | None
    progress_done: int
    progress_total: int
    cover_path: str | None
    error_summary: str | None
    created_at: datetime
    updated_at: datetime


class BlockRead(BaseModel):
    id: UUID
    type: str
    bbox_px: dict
    bbox_norm: dict
    polygon_px: dict | None
    confidence: float | None
    color_key: str
    raw_surya: dict
    result: dict | None
    artifact_path: str | None
    sort_order: int


class DetectionBoxRead(BaseModel):
    id: UUID
    bbox_px: dict
    bbox_norm: dict
    polygon_px: dict | None
    confidence: float | None
    raw_surya: dict
    sort_order: int


class PageRead(BaseModel):
    id: UUID
    page_number: int
    width_px: int | None
    height_px: int | None
    image_path: str | None
    status: PageStatus
    error_message: str | None
    blocks: list[BlockRead]
    detections: list[DetectionBoxRead]


class PageListResponse(BaseModel):
    total: int
    items: list[PageRead]
