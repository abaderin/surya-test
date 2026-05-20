from dataclasses import dataclass
from pathlib import Path
from random import Random

import fitz
from pypdf import PdfReader


@dataclass
class LayoutBlock:
    block_type: str
    bbox_px: dict
    bbox_norm: dict
    confidence: float
    raw: dict


@dataclass
class RenderedPage:
    width_px: int
    height_px: int
    dpi: int
    format: str


class ProcessorService:
    """Runtime adapter boundary. Surya can replace these internals."""

    def __init__(self) -> None:
        self._rnd = Random(7)

    def validate_pdf(self, source_path: str) -> int:
        reader = PdfReader(source_path)
        pages = len(reader.pages)
        if pages <= 0:
            raise ValueError("PDF has no pages")
        return pages

    def render_page(self, source_path: str, page_number: int, output_path: str, dpi: int = 144) -> RenderedPage:
        if page_number <= 0:
            raise ValueError("page_number must be >= 1")
        zoom = dpi / 72
        source = Path(source_path)
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with fitz.open(source) as doc:
            if page_number > doc.page_count:
                raise ValueError(f"page {page_number} out of range (total={doc.page_count})")
            page = doc[page_number - 1]
            pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            pixmap.save(target)
            return RenderedPage(
                width_px=pixmap.width,
                height_px=pixmap.height,
                dpi=dpi,
                format="png",
            )

    def layout(self, page_path: str, width: int, height: int) -> list[LayoutBlock]:
        _ = page_path
        blocks: list[LayoutBlock] = []
        for idx, block_type in enumerate(["text", "header", "image"]):
            x = 20 + idx * 140
            y = 30 + idx * 110
            w = 220
            h = 80
            blocks.append(
                LayoutBlock(
                    block_type=block_type,
                    bbox_px={"x": x, "y": y, "width": w, "height": h},
                    bbox_norm={
                        "x": round(x / width, 6),
                        "y": round(y / height, 6),
                        "width": round(w / width, 6),
                        "height": round(h / height, 6),
                    },
                    confidence=round(self._rnd.uniform(0.7, 0.99), 4),
                    raw={"type": block_type, "bbox": [x, y, x + w, y + h]},
                )
            )
        return blocks

    def ocr(self, block_type: str) -> dict:
        if block_type in {"text", "header"}:
            return {"text": f"Detected {block_type} content"}
        return {}

    def image_extraction(self, block_type: str) -> dict:
        if block_type == "image":
            return {"image_note": "image extraction placeholder"}
        return {}
