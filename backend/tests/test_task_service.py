import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

import app.services.task_service as task_service_module
from app.models.block import Block
from app.models.enums import FileStatus, PageStatus, TaskStatus, TaskType
from app.models.file import File
from app.models.page import Page
from app.models.task import Task
from app.services.task_service import (
    FILE_TERMINAL_STATUSES,
    TASK_TERMINAL_STATUSES,
    _bbox_center,
    _contains_point,
    _intersection_area,
    color_for_block_type,
    ocr_block_ids_from_payload,
    should_enqueue_image_extraction,
    should_enqueue_ocr,
)


class FakeRenderSession:
    def __init__(self, file: File, page: Page) -> None:
        self.file = file
        self.page = page
        self.added: list[object] = []
        self.commits = 0
        self.flushes = 0

    async def get(self, model, id):
        if model is Page and id == self.page.id:
            return self.page
        if model is File and id == self.file.id:
            return self.file
        return None

    def add(self, item: object) -> None:
        self.added.append(item)

    async def flush(self) -> None:
        self.flushes += 1

    async def commit(self) -> None:
        self.commits += 1


class FakeRenderStorage:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.replaced: tuple[Path, Path] | None = None

    def resolve_media_path(self, rel_path: str) -> Path:
        return self.root / rel_path

    def page_image_rel_path(self, file_id: uuid.UUID, page_number: int, ext: str) -> str:
        return f"pages/{file_id}/{page_number}.{ext}"

    def atomic_replace(self, source: Path, target: Path) -> None:
        self.replaced = (source, target)


class FakeRenderProcessor:
    def __init__(self) -> None:
        self.call: tuple[str, int, str, int] | None = None

    def render_page(self, source_path: str, page_number: int, output_path: str, dpi: int):
        self.call = (source_path, page_number, output_path, dpi)
        return SimpleNamespace(width_px=2550, height_px=3300, dpi=dpi, format="png")


class FakeOcrBatchSession:
    def __init__(self, pages: list[Page], blocks: list[Block]) -> None:
        self.pages = {page.id: page for page in pages}
        self.blocks = {block.id: block for block in blocks}
        self.commits = 0
        self.flushes = 0

    async def get(self, model, id):
        if model is Page:
            return self.pages.get(id)
        if model is Block:
            return self.blocks.get(id)
        return None

    async def flush(self) -> None:
        self.flushes += 1

    async def commit(self) -> None:
        self.commits += 1


class FakeOcrBatchStorage:
    def resolve_media_path(self, rel_path: str) -> Path:
        return Path("/tmp") / rel_path


class FakeOcrBatchProcessor:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def ocr_page_many(self, page_paths: list[str]) -> list[list[dict]]:
        self.calls.append(page_paths)
        return [
            [
                {
                    "text": "First",
                    "bbox_px": {"x": 10, "y": 10, "width": 20, "height": 20},
                    "raw_surya_ocr": {"text": "First"},
                }
            ],
            [
                {
                    "text": "Second",
                    "bbox_px": {"x": 110, "y": 10, "width": 20, "height": 20},
                    "raw_surya_ocr": {"text": "Second"},
                }
            ],
        ]


class RecordingTaskService(task_service_module.TaskService):
    def __init__(self, session, storage, processor) -> None:
        super().__init__(session, storage, processor)
        self.recalculated_file_ids: list[uuid.UUID] = []

    async def _recalc_progress(self, file_id: uuid.UUID) -> None:
        self.recalculated_file_ids.append(file_id)


def test_color_for_block_type_maps_surya_labels() -> None:
    assert color_for_block_type("Text") == "blue"
    assert color_for_block_type("SectionHeader") == "red"
    assert color_for_block_type("Picture") == "green"
    assert color_for_block_type("Caption") == "orange"
    assert color_for_block_type("PageFooter") == "gray"
    assert color_for_block_type("Table") == "purple"
    assert color_for_block_type("UnknownLabel") == "gray"


def test_should_enqueue_ocr_for_supported_labels() -> None:
    assert should_enqueue_ocr("Text") is True
    assert should_enqueue_ocr("SectionHeader") is True
    assert should_enqueue_ocr("ListItem") is True
    assert should_enqueue_ocr("PageHeader") is True
    assert should_enqueue_ocr("Equation") is True
    assert should_enqueue_ocr("Caption") is True
    assert should_enqueue_ocr("Footnote") is True
    assert should_enqueue_ocr("Code") is True
    assert should_enqueue_ocr("Form") is True
    assert should_enqueue_ocr(" sectionheader ") is True
    assert should_enqueue_ocr("Picture") is False
    assert should_enqueue_ocr("Table") is False
    assert should_enqueue_ocr("UnknownLabel") is False


def test_should_enqueue_image_extraction_only_for_picture_label() -> None:
    assert should_enqueue_image_extraction("Picture") is True
    assert should_enqueue_image_extraction("Figure") is False
    assert should_enqueue_image_extraction("Text") is False


def test_ocr_block_ids_from_payload_supports_new_block_ids() -> None:
    first = uuid.uuid4()
    second = uuid.uuid4()
    assert ocr_block_ids_from_payload({"block_ids": [str(first), str(second)]}) == [first, second]


def test_ocr_block_ids_from_payload_supports_legacy_block_id() -> None:
    value = uuid.uuid4()
    assert ocr_block_ids_from_payload({"block_id": str(value)}) == [value]


def test_bbox_center_returns_midpoint() -> None:
    assert _bbox_center({"x": 10, "y": 20, "width": 30, "height": 40}) == (25.0, 40.0)


def test_contains_point_accepts_inside_and_rejects_outside() -> None:
    bbox = {"x": 10, "y": 20, "width": 30, "height": 40}
    assert _contains_point(bbox, 20.0, 30.0) is True
    assert _contains_point(bbox, 200.0, 300.0) is False


def test_intersection_area_returns_overlap_area() -> None:
    a = {"x": 10, "y": 10, "width": 50, "height": 50}
    b = {"x": 40, "y": 30, "width": 40, "height": 40}
    assert _intersection_area(a, b) == 600.0


def test_cancel_statuses_are_available() -> None:
    assert FileStatus.CANCELLING.value == "cancelling"
    assert FileStatus.CANCELLED.value == "cancelled"
    assert TaskStatus.CANCELLED.value == "cancelled"


def test_terminal_status_sets_include_cancelled() -> None:
    assert FileStatus.CANCELLED in FILE_TERMINAL_STATUSES
    assert TaskStatus.CANCELLED in TASK_TERMINAL_STATUSES


@pytest.mark.asyncio
async def test_execute_render_uses_configured_page_render_dpi(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(task_service_module.settings, "page_render_dpi", 300)
    file = File(
        id=uuid.uuid4(),
        filename="book.pdf",
        content_type="application/pdf",
        size_bytes=100,
        status=FileStatus.IN_PROGRESS,
        source_path="originals/book.pdf",
        progress_done=0,
        progress_total=3,
    )
    page = Page(id=uuid.uuid4(), file_id=file.id, page_number=11, status=PageStatus.NEW)
    task = Task(
        id=uuid.uuid4(),
        file_id=file.id,
        page_id=page.id,
        type=TaskType.RENDER_PAGE,
        status=TaskStatus.IN_PROGRESS,
        input_payload={"page_number": page.page_number},
    )
    session = FakeRenderSession(file, page)
    storage = FakeRenderStorage(tmp_path)
    processor = FakeRenderProcessor()
    service = task_service_module.TaskService(session, storage, processor)

    await service._execute_render(task)

    assert processor.call is not None
    assert processor.call[3] == 300
    assert page.width_px == 2550
    assert page.height_px == 3300
    assert page.image_path == f"pages/{file.id}/11.png"
    assert task.output_payload["dpi"] == 300
    assert [item.type for item in session.added if isinstance(item, Task)] == [TaskType.LAYOUT, TaskType.DETECTION]


@pytest.mark.asyncio
async def test_execute_ocr_tasks_batches_pages_and_updates_blocks() -> None:
    file_id = uuid.uuid4()
    page_one = Page(id=uuid.uuid4(), file_id=file_id, page_number=1, status=PageStatus.DONE, image_path="pages/1.png")
    page_two = Page(id=uuid.uuid4(), file_id=file_id, page_number=2, status=PageStatus.DONE, image_path="pages/2.png")
    block_one = Block(
        id=uuid.uuid4(),
        file_id=file_id,
        page_id=page_one.id,
        page_number=1,
        type="Text",
        bbox_px={"x": 0, "y": 0, "width": 60, "height": 60},
        bbox_norm={"x": 0, "y": 0, "width": 1, "height": 1},
        color_key="blue",
        raw_surya={},
        sort_order=0,
    )
    block_two = Block(
        id=uuid.uuid4(),
        file_id=file_id,
        page_id=page_two.id,
        page_number=2,
        type="Text",
        bbox_px={"x": 100, "y": 0, "width": 60, "height": 60},
        bbox_norm={"x": 0, "y": 0, "width": 1, "height": 1},
        color_key="blue",
        raw_surya={},
        sort_order=0,
    )
    task_one = Task(
        id=uuid.uuid4(),
        file_id=file_id,
        page_id=page_one.id,
        type=TaskType.OCR,
        status=TaskStatus.IN_PROGRESS,
        input_payload={"block_ids": [str(block_one.id)]},
    )
    task_two = Task(
        id=uuid.uuid4(),
        file_id=file_id,
        page_id=page_two.id,
        type=TaskType.OCR,
        status=TaskStatus.IN_PROGRESS,
        input_payload={"block_ids": [str(block_two.id)]},
    )
    session = FakeOcrBatchSession([page_one, page_two], [block_one, block_two])
    processor = FakeOcrBatchProcessor()
    service = RecordingTaskService(session, FakeOcrBatchStorage(), processor)

    await service.execute_ocr_tasks([task_one, task_two])

    assert processor.calls == [["/tmp/pages/1.png", "/tmp/pages/2.png"]]
    assert task_one.status == TaskStatus.DONE
    assert task_two.status == TaskStatus.DONE
    assert task_one.output_payload == {"blocks": 1, "text_blocks": 1, "lines": 1, "unassigned_lines": 0}
    assert task_two.output_payload == {"blocks": 1, "text_blocks": 1, "lines": 1, "unassigned_lines": 0}
    assert block_one.result["text"] == "First"
    assert block_two.result["text"] == "Second"
    assert service.recalculated_file_ids == [file_id]
