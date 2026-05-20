from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File as UploadFileArg, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_event_bus, get_processor, get_storage
from app.models.block import Block
from app.models.enums import FileStatus
from app.models.file import File
from app.models.page import Page
from app.schemas.files import BlockRead, FileRead, PageListResponse, PageRead
from app.services.task_service import TaskService

router = APIRouter(prefix="/api/files", tags=["files"])


@router.post("", response_model=FileRead)
async def upload_file(
    upload: UploadFile = UploadFileArg(...),
    db: AsyncSession = Depends(get_db),
) -> FileRead:
    event_bus = await get_event_bus()
    service = TaskService(db, get_storage(), get_processor(), event_bus)
    file = await service.create_upload(upload.filename or "unknown.pdf", upload.content_type or "application/pdf", 0)
    source_path, sha256, size_bytes = await get_storage().save_source(file.id, upload)
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
    return [FileRead.model_validate(it, from_attributes=True) for it in items]


@router.get("/{file_id}", response_model=FileRead)
async def get_file(file_id: UUID, db: AsyncSession = Depends(get_db)) -> FileRead:
    model = await db.get(File, file_id)
    if not model:
        raise HTTPException(status_code=404, detail="file not found")
    return FileRead.model_validate(model, from_attributes=True)


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
            )
        )
    return PageListResponse(total=total, items=items)


async def media_file(path: str) -> FileResponse:
    try:
        resolved = get_storage().resolve_media_path(path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid path") from exc
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=404, detail="media not found")
    return FileResponse(Path(resolved))
