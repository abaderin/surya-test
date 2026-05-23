from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File as UploadFileArg, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_storage, get_task_service
from app.models.block import Block
from app.models.detection_box import DetectionBox
from app.models.enums import FileStatus, TaskStatus
from app.models.file import File
from app.models.page import Page
from app.models.task import Task
from app.schemas.files import BlockRead, DetectionBoxRead, FileRead, PageListResponse, PageRead
from app.services.storage import StorageService
from app.services.task_service import TaskService

router = APIRouter(prefix="/api/files", tags=["files"])
TASK_STATUS_KEYS: dict[TaskStatus, str] = {
    TaskStatus.NEW: "new",
    TaskStatus.DONE: "done",
    TaskStatus.FAILED: "failed",
}


def _empty_task_status_counts() -> dict[str, int]:
    return {"new": 0, "done": 0, "failed": 0}


async def _load_task_status_counts(db: AsyncSession, file_ids: list[UUID]) -> dict[UUID, dict[str, int]]:
    if not file_ids:
        return {}
    rows = await db.execute(
        select(Task.file_id, Task.status, func.count())
        .where(
            and_(
                Task.deleted.is_(False),
                Task.file_id.in_(file_ids),
                Task.status.in_(tuple(TASK_STATUS_KEYS.keys())),
            )
        )
        .group_by(Task.file_id, Task.status)
    )
    counts_by_file_id = {file_id: _empty_task_status_counts() for file_id in file_ids}
    for file_id, status, count in rows.all():
        key = TASK_STATUS_KEYS.get(status)
        if key is not None:
            counts_by_file_id[file_id][key] = int(count)
    return counts_by_file_id


@router.post("", response_model=FileRead)
async def upload_file(
    upload: UploadFile = UploadFileArg(...),
    db: AsyncSession = Depends(get_db),
    service: TaskService = Depends(get_task_service),
    storage: StorageService = Depends(get_storage),
) -> FileRead:
    file = await service.create_upload(upload.filename or "unknown.pdf", upload.content_type or "application/pdf", 0)
    source_path, sha256, size_bytes = await storage.save_source(file.id, upload)
    await service.enqueue_after_upload(file.id, source_path, sha256, size_bytes)
    await db.refresh(file)
    return FileRead.model_validate(file, from_attributes=True)


@router.get("", response_model=list[FileRead])
async def list_files(
    status: FileStatus | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[FileRead]:
    query = select(File).order_by(File.created_at.desc()).limit(limit).offset(offset)
    if status:
        query = query.where(File.status == status)
    items = (await db.execute(query)).scalars().all()
    counts_by_file_id = await _load_task_status_counts(db, [item.id for item in items])
    response_items: list[FileRead] = []
    for item in items:
        payload = FileRead.model_validate(item, from_attributes=True)
        payload.task_status_counts = counts_by_file_id.get(item.id, _empty_task_status_counts())
        response_items.append(payload)
    return response_items


@router.get("/{file_id}", response_model=FileRead)
async def get_file(file_id: UUID, db: AsyncSession = Depends(get_db)) -> FileRead:
    model = await db.get(File, file_id)
    if not model:
        raise HTTPException(status_code=404, detail="file not found")
    payload = FileRead.model_validate(model, from_attributes=True)
    payload.task_status_counts = (await _load_task_status_counts(db, [model.id])).get(model.id, _empty_task_status_counts())
    return payload


@router.post("/{file_id}/reprocess", response_model=FileRead)
async def reprocess_file(
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
    service: TaskService = Depends(get_task_service),
) -> FileRead:
    try:
        model = await service.reprocess_file(file_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await db.refresh(model)
    return FileRead.model_validate(model, from_attributes=True)


@router.post("/{file_id}/cancel", response_model=FileRead)
async def cancel_file(
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
    service: TaskService = Depends(get_task_service),
) -> FileRead:
    try:
        model = await service.cancel_file(file_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await db.refresh(model)
    return FileRead.model_validate(model, from_attributes=True)


@router.delete("/{file_id}", status_code=204, response_class=Response)
async def delete_file(
    file_id: UUID,
    service: TaskService = Depends(get_task_service),
) -> Response:
    try:
        await service.delete_file(file_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(status_code=204)


@router.get("/{file_id}/pages", response_model=PageListResponse)
async def list_pages(
    file_id: UUID,
    limit: int = Query(default=10, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> PageListResponse:
    total = int(await db.scalar(select(func.count()).select_from(Page).where(Page.file_id == file_id)) or 0)
    pages = (
        await db.execute(
            select(Page).where(Page.file_id == file_id).order_by(Page.page_number).limit(limit).offset(offset)
        )
    ).scalars().all()
    items: list[PageRead] = []
    for page in pages:
        blocks = (
            await db.execute(select(Block).where(Block.page_id == page.id).order_by(Block.sort_order))
        ).scalars().all()
        detections = (
            await db.execute(select(DetectionBox).where(DetectionBox.page_id == page.id).order_by(DetectionBox.sort_order))
        ).scalars().all()
        items.append(
            PageRead(
                id=page.id,
                page_number=page.page_number,
                width_px=page.width_px,
                height_px=page.height_px,
                image_path=page.image_path,
                status=page.status,
                error_message=page.error_message,
                blocks=[BlockRead.model_validate(b, from_attributes=True) for b in blocks],
                detections=[DetectionBoxRead.model_validate(d, from_attributes=True) for d in detections],
            )
        )
    return PageListResponse(total=total, items=items)


async def media_file(path: str, storage: StorageService) -> FileResponse:
    try:
        resolved = storage.resolve_media_path(path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid path") from exc
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=404, detail="media not found")
    return FileResponse(Path(resolved))
