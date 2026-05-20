from app.core.settings import Settings
from app.models.enums import TaskType


def test_worker_task_types_set_is_none_by_default() -> None:
    settings = Settings(worker_task_types=None)
    assert settings.worker_task_types_set is None


def test_worker_task_types_set_parses_layout() -> None:
    settings = Settings(worker_task_types="layout")
    assert settings.worker_task_types_set == {TaskType.LAYOUT}


def test_worker_task_types_set_parses_multiple_values() -> None:
    settings = Settings(worker_task_types="validation, render_page ,ocr")
    assert settings.worker_task_types_set == {
        TaskType.VALIDATION,
        TaskType.RENDER_PAGE,
        TaskType.OCR,
    }
