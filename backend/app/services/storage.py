import hashlib
import os
import shutil
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile

from app.core.settings import settings


class StorageService:
    def __init__(self) -> None:
        self.root = settings.storage_root_path
        self.root.mkdir(parents=True, exist_ok=True)

    def _abs(self, rel_path: str) -> Path:
        full = (self.root / rel_path).resolve()
        if self.root not in full.parents and full != self.root:
            raise ValueError("invalid path")
        return full

    async def save_source(self, file_id: UUID, upload: UploadFile) -> tuple[str, str, int]:
        directory = self._abs(f"originals/{file_id}")
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / "source.pdf"
        hasher = hashlib.sha256()
        total = 0
        with target.open("wb") as f:
            while chunk := await upload.read(1024 * 1024):
                hasher.update(chunk)
                total += len(chunk)
                f.write(chunk)
        return str(target.relative_to(self.root)), hasher.hexdigest(), total

    def page_image_rel_path(self, file_id: UUID, page_number: int, ext: str = "png") -> str:
        directory = self._abs(f"pages/{file_id}")
        directory.mkdir(parents=True, exist_ok=True)
        return str((directory / f"{page_number}.{ext}").relative_to(self.root))

    def page_image_abs_path(self, file_id: UUID, page_number: int, ext: str = "png") -> Path:
        return self._abs(self.page_image_rel_path(file_id, page_number, ext))

    def atomic_replace(self, tmp_path: Path, target_path: Path) -> None:
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(tmp_path, target_path)

    def save_cover_placeholder(self, file_id: UUID) -> str:
        directory = self._abs(f"thumbs/{file_id}")
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / "cover.svg"
        target.write_text(
            (
                "<svg xmlns='http://www.w3.org/2000/svg' width='360' height='520'>"
                "<rect width='360' height='520' fill='#f4f6fa'/>"
                "<rect x='20' y='20' width='320' height='480' fill='none' stroke='#adb5bd'/>"
                "<text x='40' y='90' font-size='28' fill='#495057'>Book</text>"
                "</svg>"
            ),
            encoding="utf-8",
        )
        return str(target.relative_to(self.root))

    def resolve_media_path(self, rel_path: str) -> Path:
        return self._abs(rel_path)

    def remove_generated_artifacts(self, file_id: UUID) -> None:
        for rel_dir in (f"pages/{file_id}", f"thumbs/{file_id}"):
            target = self._abs(rel_dir)
            if target.exists():
                shutil.rmtree(target)
