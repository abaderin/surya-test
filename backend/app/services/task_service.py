from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.block import Block
from app.models.enums import FileStatus, PageStatus, TaskStatus, TaskType
from app.models.file import File
from app.models.page import Page
from app.models.task import Task
from app.services.events import EventBus
from app.services.processor import ProcessorService
from app.services.storage import StorageService

COLOR_MAP = {"text": "blue", "header": "red", "image": "green"}


class TaskService:
    def __init__(
        self,
        session: AsyncSession,
        storage: StorageService,
        processor: ProcessorService,
        bus: EventBus | None = None,
    ) -> None:
        self.session = session
        self.storage = storage
        self.processor = processor
        self.bus = bus

    async def create_upload(self, filename: str, content_type: str, size_bytes: int) -> File:
        file = File(
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            status=FileStatus.NEW,
            progress_done=0,
            progress_total=1,
        )
        self.session.add(file)
        await self.session.commit()
        await self._emit(file.id, "file.updated", {"status": file.status})
        return file

    async def enqueue_after_upload(self, file_id: UUID, source_path: str, sha256: str, size_bytes: int) -> None:
        file = await self.session.get(File, file_id)
        if not file:
            return
        file.source_path = source_path
        file.sha256 = sha256
        file.size_bytes = size_bytes
        file.status = FileStatus.VALIDATION
        self.session.add(
            Task(
                file_id=file.id,
                type=TaskType.VALIDATION,
                status=TaskStatus.NEW,
                input_payload={"file_id": str(file.id)},
            )
        )
        await self.session.commit()
        await self._emit(file.id, "file.updated", {"status": file.status})

    async def claim_next_task(self, stale_after_seconds: int) -> Task | None:
        stale_threshold = datetime.now(UTC) - timedelta(seconds=stale_after_seconds)
        await self.session.execute(
            update(Task)
            .where(and_(Task.status == TaskStatus.IN_PROGRESS, Task.started_at < stale_threshold))
            .values(status=TaskStatus.NEW)
        )
        await self.session.commit()

        result = await self.session.execute(
            select(Task).where(Task.status == TaskStatus.NEW).order_by(Task.created_at).limit(1).with_for_update(skip_locked=True)
        )
        task = result.scalar_one_or_none()
        if not task:
            return None
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.now(UTC)
        task.attempts += 1
        await self.session.commit()
        return task

    async def execute_task(self, task: Task) -> None:
        try:
            if task.type == TaskType.VALIDATION:
                await self._execute_validation(task)
            elif task.type == TaskType.RENDER_PAGE:
                await self._execute_render(task)
            elif task.type == TaskType.LAYOUT:
                await self._execute_layout(task)
            elif task.type == TaskType.OCR:
                await self._execute_ocr(task)
            elif task.type in {TaskType.IMAGE_EXTRACTION, TaskType.META_EXTRACTION}:
                task.output_payload = {"ok": True}
            task.status = TaskStatus.DONE
            task.finished_at = datetime.now(UTC)
            await self.session.commit()
            if task.file_id:
                await self._recalc_progress(task.file_id)
        except Exception as exc:  # noqa: BLE001
            task.status = TaskStatus.FAILED
            task.error_message = str(exc)
            task.finished_at = datetime.now(UTC)
            await self.session.commit()
            if task.page_id:
                page = await self.session.get(Page, task.page_id)
                if page:
                    page.status = PageStatus.FAILED
                    page.error_message = str(exc)
                    await self.session.commit()
            if task.file_id and not task.page_id:
                file = await self.session.get(File, task.file_id)
                if file and file.status != FileStatus.VALIDATION_FAILED:
                    file.status = FileStatus.FAILED
                    file.error_summary = str(exc)
                    await self.session.commit()
            if task.file_id:
                await self._emit(task.file_id, "task.updated", {"task_id": str(task.id), "status": task.status})

    async def _execute_validation(self, task: Task) -> None:
        if not task.file_id:
            raise ValueError("task has no file")
        file = await self.session.get(File, task.file_id)
        if not file:
            raise ValueError("file not found")
        if file.content_type not in {"application/pdf", "application/x-pdf"} and not file.filename.lower().endswith(".pdf"):
            file.status = FileStatus.VALIDATION_FAILED
            file.error_summary = "Only PDF is supported in MVP"
            task.output_payload = {"pages_count": 0}
            await self.session.commit()
            return
        if not file.source_path:
            raise ValueError("source path missing")
        source_abs_path = self.storage.resolve_media_path(file.source_path)
        pages_count = self.processor.validate_pdf(str(source_abs_path))
        file.pages_count = pages_count
        file.status = FileStatus.IN_PROGRESS
        file.progress_total = 1 + pages_count * 2
        file.cover_path = self.storage.save_cover_placeholder(file.id)
        self.session.add(file)

        for page_number in range(1, pages_count + 1):
            page = Page(
                file_id=file.id,
                page_number=page_number,
                status=PageStatus.NEW,
            )
            self.session.add(page)
            await self.session.flush()
            self.session.add(
                Task(
                    file_id=file.id,
                    page_id=page.id,
                    type=TaskType.RENDER_PAGE,
                    status=TaskStatus.NEW,
                    input_payload={"page_number": page_number},
                )
            )
        task.output_payload = {"pages_count": pages_count}
        await self.session.commit()
        await self._emit(file.id, "file.updated", {"status": file.status, "pages_count": pages_count})

    async def _execute_render(self, task: Task) -> None:
        page = await self.session.get(Page, task.page_id)
        if not page:
            raise ValueError("page not found")
        file = await self.session.get(File, page.file_id)
        if not file:
            raise ValueError("file not found")
        if not file.source_path:
            raise ValueError("source path missing")
        page.status = PageStatus.IN_PROGRESS
        source_abs_path = self.storage.resolve_media_path(file.source_path)
        target_rel_path = self.storage.page_image_rel_path(page.file_id, page.page_number, "png")
        target_abs_path = self.storage.resolve_media_path(target_rel_path)
        tmp_abs_path = target_abs_path.with_name(f"{target_abs_path.stem}.tmp{target_abs_path.suffix}")
        rendered = self.processor.render_page(str(source_abs_path), page.page_number, str(tmp_abs_path), dpi=144)
        self.storage.atomic_replace(tmp_abs_path, target_abs_path)
        page.image_path = target_rel_path
        page.width_px = rendered.width_px
        page.height_px = rendered.height_px
        page.status = PageStatus.DONE
        await self.session.flush()
        self.session.add(
            Task(
                file_id=page.file_id,
                page_id=page.id,
                type=TaskType.LAYOUT,
                status=TaskStatus.NEW,
                input_payload={"page_number": page.page_number},
            )
        )
        task.output_payload = {
            "image_path": page.image_path,
            "width_px": rendered.width_px,
            "height_px": rendered.height_px,
            "dpi": rendered.dpi,
            "format": rendered.format,
        }
        await self.session.commit()
        await self._emit(page.file_id, "page.updated", {"page_id": str(page.id), "status": page.status})

    async def _execute_layout(self, task: Task) -> None:
        page = await self.session.get(Page, task.page_id)
        if not page:
            raise ValueError("page not found")
        if not page.image_path or not page.width_px or not page.height_px:
            raise ValueError("page image not ready")
        blocks = self.processor.layout(page.image_path, page.width_px, page.height_px)
        for i, block in enumerate(blocks):
            model = Block(
                file_id=page.file_id,
                page_id=page.id,
                page_number=page.page_number,
                type=block.block_type,
                bbox_px=block.bbox_px,
                bbox_norm=block.bbox_norm,
                polygon_px=None,
                confidence=block.confidence,
                color_key=COLOR_MAP.get(block.block_type, "gray"),
                raw_surya=block.raw,
                sort_order=i,
            )
            self.session.add(model)
            await self.session.flush()
            self.session.add(
                Task(
                    file_id=page.file_id,
                    page_id=page.id,
                    type=TaskType.OCR,
                    status=TaskStatus.NEW,
                    input_payload={"block_id": str(model.id), "type": model.type},
                )
            )
        task.output_payload = {"blocks": len(blocks)}
        await self.session.commit()

    async def _execute_ocr(self, task: Task) -> None:
        block_id = task.input_payload.get("block_id")
        if not block_id:
            task.output_payload = {"skipped": True}
            return
        block = await self.session.get(Block, UUID(block_id))
        if not block:
            raise ValueError("block not found")
        ocr = self.processor.ocr(block.type)
        block.result = {**(block.result or {}), **ocr}
        task.output_payload = ocr
        await self.session.flush()

    async def _recalc_progress(self, file_id: UUID) -> None:
        file = await self.session.get(File, file_id)
        if not file:
            return
        done = await self.session.scalar(
            select(func.count()).select_from(Task).where(and_(Task.file_id == file_id, Task.status == TaskStatus.DONE))
        )
        total = await self.session.scalar(select(func.count()).select_from(Task).where(Task.file_id == file_id))
        file.progress_done = int(done or 0)
        file.progress_total = int(total or 0)
        if (
            file.status not in {FileStatus.VALIDATION_FAILED, FileStatus.FAILED}
            and file.progress_total > 0
            and file.progress_done >= file.progress_total
        ):
            file.status = FileStatus.DONE
        await self.session.commit()
        await self._emit(
            file_id,
            "processing.progress",
            {"done": file.progress_done, "total": file.progress_total, "status": file.status},
        )

    async def _emit(self, file_id: UUID, event_type: str, payload: dict) -> None:
        if self.bus:
            await self.bus.publish(file_id, event_type, payload)
