from app.core.settings import Settings
from app.models.enums import TaskType
import pytest


def test_worker_task_types_set_is_none_by_default() -> None:
    settings = Settings(worker_task_types=None)
    assert settings.worker_task_types_set is None


def test_worker_task_types_set_parses_layout() -> None:
    settings = Settings(worker_task_types="layout")
    assert settings.worker_task_types_set == {TaskType.LAYOUT}


def test_worker_task_types_set_parses_multiple_values() -> None:
    settings = Settings(worker_task_types="validation, render_page ,ocr,detection")
    assert settings.worker_task_types_set == {
        TaskType.VALIDATION,
        TaskType.RENDER_PAGE,
        TaskType.OCR,
        TaskType.DETECTION,
    }


def test_cpu_threads_must_be_positive() -> None:
    with pytest.raises(ValueError):
        Settings(cpu_threads=0)


def test_page_render_dpi_defaults_to_notebook_resolution() -> None:
    settings = Settings()
    assert settings.page_render_dpi == 300


def test_page_render_dpi_must_not_be_too_low() -> None:
    with pytest.raises(ValueError):
        Settings(page_render_dpi=71)
