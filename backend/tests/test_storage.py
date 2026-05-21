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


def test_remove_generated_artifacts_removes_pages_and_thumbs_only(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(storage_module.settings, "storage_root", str(tmp_path))
    service = StorageService()
    file_id = uuid4()

    pages = tmp_path / "pages" / str(file_id)
    thumbs = tmp_path / "thumbs" / str(file_id)
    originals = tmp_path / "originals" / str(file_id)
    pages.mkdir(parents=True)
    thumbs.mkdir(parents=True)
    originals.mkdir(parents=True)
    (pages / "1.png").write_text("x", encoding="utf-8")
    (thumbs / "cover.svg").write_text("x", encoding="utf-8")
    (originals / "source.pdf").write_text("x", encoding="utf-8")

    service.remove_generated_artifacts(file_id)

    assert not pages.exists()
    assert not thumbs.exists()
    assert originals.exists()
    assert (originals / "source.pdf").exists()


def test_remove_file_resources_removes_originals_pages_and_thumbs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(storage_module.settings, "storage_root", str(tmp_path))
    service = StorageService()
    file_id = uuid4()

    pages = tmp_path / "pages" / str(file_id)
    thumbs = tmp_path / "thumbs" / str(file_id)
    originals = tmp_path / "originals" / str(file_id)
    pages.mkdir(parents=True)
    thumbs.mkdir(parents=True)
    originals.mkdir(parents=True)
    (pages / "1.png").write_text("x", encoding="utf-8")
    (thumbs / "cover.svg").write_text("x", encoding="utf-8")
    (originals / "source.pdf").write_text("x", encoding="utf-8")

    service.remove_file_resources(file_id)

    assert not pages.exists()
    assert not thumbs.exists()
    assert not originals.exists()


def test_block_artifact_path_is_inside_blocks_root(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(storage_module.settings, "storage_root", str(tmp_path))
    service = StorageService()
    file_id = uuid4()
    block_id = uuid4()

    rel = service.block_artifact_rel_path(file_id, block_id, ext="png")
    abs_path = service.resolve_media_path(rel)

    assert rel == f"blocks/{file_id}/{block_id}.png"
    assert abs_path == tmp_path / rel
