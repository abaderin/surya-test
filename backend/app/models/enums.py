from enum import StrEnum

from sqlalchemy import Enum as SAEnum


class FileStatus(StrEnum):
    NEW = "new"
    VALIDATION = "validation"
    VALIDATION_FAILED = "validation_failed"
    IN_PROGRESS = "in_progress"
    FAILED = "failed"
    DONE = "done"


class TaskStatus(StrEnum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    FAILED = "failed"
    DONE = "done"


class PageStatus(StrEnum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    FAILED = "failed"
    DONE = "done"


class TaskType(StrEnum):
    VALIDATION = "validation"
    RENDER_PAGE = "render_page"
    LAYOUT = "layout"
    DETECTION = "detection"
    OCR = "ocr"
    IMAGE_EXTRACTION = "image_extraction"
    META_EXTRACTION = "meta_extraction"


def db_enum(enum_cls: type[StrEnum], name: str) -> SAEnum:
    return SAEnum(
        enum_cls,
        name=name,
        values_callable=lambda items: [item.value for item in items],
        validate_strings=True,
    )
