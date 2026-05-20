from pathlib import Path
from uuid import uuid4

import pytest
import app.services.storage as storage_module
from app.services.storage import StorageService


def test_page_image_path_is_inside_pages_root(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(storage_module.settings, "storage_root", str(tmp_path))
    service = StorageService()
    file_id = uuid4()

    rel = service.page_image_rel_path(file_id, page_number=3, ext="png")
    abs_path = service.resolve_media_path(rel)

    assert rel == f"pages/{file_id}/3.png"
    assert abs_path == tmp_path / rel


def test_resolve_media_path_blocks_traversal(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(storage_module.settings, "storage_root", str(tmp_path))
    service = StorageService()

    with pytest.raises(ValueError):
        service.resolve_media_path("../etc/passwd")
