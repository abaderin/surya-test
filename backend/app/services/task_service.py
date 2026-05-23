import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.block import Block
from app.models.enums import FileStatus, PageStatus, TaskStatus, TaskType
from app.models.file import File
from app.models.page import Page
from app.models.task import Task
from app.services.events import EventBus
from app.services.processor import ProcessorService
from app.services.storage import StorageService

COLOR_MAP = {
    "text": "blue",
    "listitem": "blue",
    "code": "blue",
    "sectionheader": "red",
    "title": "red",
    "picture": "green",
    "figure": "green",
    "caption": "orange",
    "pageheader": "gray",
    "pagefooter": "gray",
    "table": "purple",
    "formula": "purple",
}

OCR_BLOCK_TYPES = frozenset(
    {
        "text",
        "sectionheader",
        "listitem",
        "pageheader",
        "equation",
        "caption",
        "footnote",
        "code",
        "form",
    }
)


def color_for_block_type(block_type: str) -> str:
    return COLOR_MAP.get(block_type.strip().lower(), "gray")


def should_enqueue_ocr(block_type: str) -> bool:
    return block_type.strip().lower() in OCR_BLOCK_TYPES


def should_enqueue_image_extraction(block_type: str) -> bool:
    return block_type == "Picture"


def ocr_block_ids_from_payload(payload: dict) -> list[UUID]:
    raw_block_ids = payload.get("block_ids")
    if isinstance(raw_block_ids, list):
        return [UUID(str(block_id)) for block_id in raw_block_ids]
    raw_block_id = payload.get("block_id")
    if raw_block_id:
        return [UUID(str(raw_block_id))]
    return []


def _bbox_center(bbox_px: dict) -> tuple[float, float]:
    return (
        float(bbox_px["x"]) + float(bbox_px["width"]) / 2.0,
        float(bbox_px["y"]) + float(bbox_px["height"]) / 2.0,
    )


def _contains_point(bbox_px: dict, x: float, y: float) -> bool:
    left = float(bbox_px["x"])
    top = float(bbox_px["y"])
    right = left + float(bbox_px["width"])
    bottom = top + float(bbox_px["height"])
    return left <= x <= right and top <= y <= bottom


def _intersection_area(a: dict, b: dict) -> float:
    ax1 = float(a["x"])
    ay1 = float(a["y"])
    ax2 = ax1 + float(a["width"])
    ay2 = ay1 + float(a["height"])
    bx1 = float(b["x"])
    by1 = float(b["y"])
    bx2 = bx1 + float(b["width"])
    by2 = by1 + float(b["height"])
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    return (ix2 - ix1) * (iy2 - iy1)


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

    async def claim_next_task(
        self,
        stale_after_seconds: int,
        allowed_types: set[TaskType] | None = None,
    ) -> Task | None:
        stale_threshold = datetime.now(UTC) - timedelta(seconds=stale_after_seconds)
        task_type_filter = (
            Task.type.in_(allowed_types)
            if allowed_types is not None
            else Task.type != TaskType.LAYOUT
        )
        await self.session.execute(
            update(Task)
            .where(
                and_(
                    Task.deleted.is_(False),
                    Task.status == TaskStatus.IN_PROGRESS,
                    Task.started_at < stale_threshold,
                    task_type_filter,
                )
            )
            .values(status=TaskStatus.NEW)
        )
        await self.session.commit()

        result = await self.session.execute(
            select(Task)
            .where(and_(Task.deleted.is_(False), Task.status == TaskStatus.NEW, task_type_filter))
            .order_by(Task.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
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
        if task.deleted:
            return
        try:
            if task.type == TaskType.VALIDATION:
                await self._execute_validation(task)
            elif task.type == TaskType.RENDER_PAGE:
                await self._execute_render(task)
            elif task.type == TaskType.LAYOUT:
                await self._execute_layout(task)
            elif task.type == TaskType.OCR:
                await self._execute_ocr(task)
            elif task.type == TaskType.IMAGE_EXTRACTION:
                await self._execute_image_extraction(task)
            elif task.type == TaskType.META_EXTRACTION:
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
        pages_count = await asyncio.to_thread(self.processor.validate_pdf, str(source_abs_path))
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
        rendered = await asyncio.to_thread(
            self.processor.render_page,
            str(source_abs_path),
            page.page_number,
            str(tmp_abs_path),
            144,
        )
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
        page.status = PageStatus.IN_PROGRESS
        page.error_message = None
        await self.session.flush()
        page_image_abs_path = self.storage.resolve_media_path(page.image_path)
        blocks = await asyncio.to_thread(self.processor.layout, str(page_image_abs_path), page.width_px, page.height_px)
        ocr_block_ids: list[str] = []
        for i, block in enumerate(blocks):
            model = Block(
                file_id=page.file_id,
                page_id=page.id,
                page_number=page.page_number,
                type=block.block_type,
                bbox_px=block.bbox_px,
                bbox_norm=block.bbox_norm,
                polygon_px=block.polygon_px,
                confidence=block.confidence,
                color_key=color_for_block_type(block.block_type),
                raw_surya=block.raw,
                sort_order=i,
            )
            self.session.add(model)
            await self.session.flush()
            if should_enqueue_ocr(model.type):
                ocr_block_ids.append(str(model.id))
            if should_enqueue_image_extraction(model.type):
                self.session.add(
                    Task(
                        file_id=page.file_id,
                        page_id=page.id,
                        type=TaskType.IMAGE_EXTRACTION,
                        status=TaskStatus.NEW,
                        input_payload={"block_id": str(model.id), "type": model.type},
                    )
                )
        if ocr_block_ids:
            self.session.add(
                Task(
                    file_id=page.file_id,
                    page_id=page.id,
                    type=TaskType.OCR,
                    status=TaskStatus.NEW,
                    input_payload={"block_ids": ocr_block_ids},
                )
            )
        page.status = PageStatus.DONE
        task.output_payload = {"blocks": len(blocks)}
        await self.session.commit()

    async def _execute_ocr(self, task: Task) -> None:
        block_ids = ocr_block_ids_from_payload(task.input_payload)
        if not block_ids:
            task.output_payload = {"skipped": True, "reason": "no_ocr_blocks"}
            return
        blocks: list[Block] = []
        for block_id in block_ids:
            block = await self.session.get(Block, block_id)
            if not block:
                raise ValueError("block not found")
            blocks.append(block)
        ocr_blocks = [block for block in blocks if should_enqueue_ocr(block.type)]
        if not ocr_blocks:
            task.output_payload = {"skipped": True, "reason": "unsupported_label"}
            return
        page = await self.session.get(Page, ocr_blocks[0].page_id)
        if not page or not page.image_path:
            raise ValueError("page image not ready")
        page_image_abs_path = self.storage.resolve_media_path(page.image_path)
        ocr_lines = await asyncio.to_thread(self.processor.ocr_page, str(page_image_abs_path))

        grouped_lines: dict[UUID, list[dict]] = {block.id: [] for block in ocr_blocks}
        unassigned_lines = 0
        for line in ocr_lines:
            line_bbox = line.get("bbox_px")
            if not isinstance(line_bbox, dict):
                continue
            cx, cy = _bbox_center(line_bbox)
            target_block: Block | None = None
            for block in ocr_blocks:
                if _contains_point(block.bbox_px, cx, cy):
                    target_block = block
                    break
            if target_block is None:
                best_score = 0.0
                for block in ocr_blocks:
                    score = _intersection_area(block.bbox_px, line_bbox)
                    if score > best_score:
                        best_score = score
                        target_block = block
            if target_block is None:
                unassigned_lines += 1
                continue
            grouped_lines[target_block.id].append(line)

        total_lines = 0
        with_text = 0
        for block in ocr_blocks:
            lines = grouped_lines[block.id]
            text_values = [str(line.get("text", "")).strip() for line in lines if str(line.get("text", "")).strip()]
            text = "\n".join(text_values)
            total_lines += len(text_values)
            if text:
                with_text += 1
            block.result = {
                **(block.result or {}),
                "text": text,
                "lines": lines,
                "raw_surya_ocr": [line.get("raw_surya_ocr") for line in lines],
            }
        task.output_payload = {
            "blocks": len(ocr_blocks),
            "text_blocks": with_text,
            "lines": total_lines,
            "unassigned_lines": unassigned_lines,
        }
        await self.session.flush()

    async def _execute_image_extraction(self, task: Task) -> None:
        block_id = task.input_payload.get("block_id")
        if not block_id:
            task.output_payload = {"skipped": True}
            return
        block = await self.session.get(Block, UUID(block_id))
        if not block:
            raise ValueError("block not found")
        if not should_enqueue_image_extraction(block.type):
            task.output_payload = {"skipped": True, "reason": "unsupported_label"}
            return
        page = await self.session.get(Page, block.page_id)
        if not page or not page.image_path:
            raise ValueError("page image not ready")
        page_image_abs_path = self.storage.resolve_media_path(page.image_path)
        artifact_rel_path = self.storage.block_artifact_rel_path(block.file_id, block.id, "png")
        artifact_abs_path = self.storage.resolve_media_path(artifact_rel_path)
        tmp_abs_path = artifact_abs_path.with_name(f"{artifact_abs_path.stem}.tmp{artifact_abs_path.suffix}")
        extracted = await asyncio.to_thread(self.processor.image_extraction, str(page_image_abs_path), block.bbox_px, str(tmp_abs_path))
        self.storage.atomic_replace(tmp_abs_path, artifact_abs_path)
        block.artifact_path = artifact_rel_path
        block.result = {
            **(block.result or {}),
            "image": {
                "path": artifact_rel_path,
                "width_px": extracted["width_px"],
                "height_px": extracted["height_px"],
                "format": extracted["format"],
            },
        }
        task.output_payload = {
            "artifact_path": artifact_rel_path,
            "width_px": extracted["width_px"],
            "height_px": extracted["height_px"],
        }
        await self.session.flush()

    async def _recalc_progress(self, file_id: UUID) -> None:
        file = await self.session.get(File, file_id)
        if not file:
            return
        done = await self.session.scalar(
            select(func.count())
            .select_from(Task)
            .where(and_(Task.file_id == file_id, Task.deleted.is_(False), Task.status == TaskStatus.DONE))
        )
        total = await self.session.scalar(
            select(func.count()).select_from(Task).where(and_(Task.file_id == file_id, Task.deleted.is_(False)))
        )
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

    async def reprocess_file(self, file_id: UUID) -> File:
        file = await self.session.get(File, file_id)
        if not file:
            raise ValueError("file not found")
        if file.status not in {FileStatus.DONE, FileStatus.FAILED, FileStatus.VALIDATION_FAILED}:
            raise RuntimeError("file is being processed")
        if not file.source_path:
            raise RuntimeError("source file is missing")

        await self.session.execute(
            update(Task)
            .where(and_(Task.file_id == file_id, Task.deleted.is_(False)))
            .values(deleted=True, page_id=None)
        )
        await self.session.execute(delete(Block).where(Block.file_id == file_id))
        await self.session.execute(delete(Page).where(Page.file_id == file_id))
        self.storage.remove_generated_artifacts(file_id)

        file.status = FileStatus.VALIDATION
        file.pages_count = None
        file.progress_done = 0
        file.progress_total = 1
        file.cover_path = None
        file.error_summary = None

        self.session.add(
            Task(
                file_id=file.id,
                type=TaskType.VALIDATION,
                status=TaskStatus.NEW,
                input_payload={"file_id": str(file.id)},
                deleted=False,
            )
        )
        await self.session.commit()
        await self._emit(file.id, "file.updated", {"status": file.status})
        return file

    async def delete_file(self, file_id: UUID) -> None:
        file = await self.session.get(File, file_id)
        if not file:
            raise ValueError("file not found")
        if file.status not in {FileStatus.DONE, FileStatus.FAILED, FileStatus.VALIDATION_FAILED}:
            raise RuntimeError("file is being processed")

        await self.session.execute(delete(Block).where(Block.file_id == file_id))
        await self.session.execute(delete(Task).where(Task.file_id == file_id))
        await self.session.execute(delete(Page).where(Page.file_id == file_id))
        await self.session.execute(delete(File).where(File.id == file_id))
        self.storage.remove_file_resources(file_id)
        await self.session.commit()
        await self._emit(file_id, "file.deleted", {"file_id": str(file_id)})
