from pathlib import Path

import pytest
from pypdf import PdfWriter

from app.services.processor import ProcessorService


def test_layout_returns_blocks_with_normalized_bbox() -> None:
    p = ProcessorService()
    blocks = p.layout("dummy", width=1200, height=1600)
    assert len(blocks) == 3
    assert blocks[0].bbox_norm["x"] < 1
    assert blocks[0].bbox_norm["y"] < 1


def test_ocr_text_for_textual_blocks() -> None:
    p = ProcessorService()
    assert "text" in p.ocr("text")
    assert p.ocr("image") == {}


def test_render_page_writes_png_and_returns_dimensions(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=600, height=800)
    with source.open("wb") as f:
        writer.write(f)

    output = tmp_path / "page-1.png"
    rendered = ProcessorService().render_page(str(source), page_number=1, output_path=str(output), dpi=144)

    assert output.exists()
    assert output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert rendered.width_px > 0
    assert rendered.height_px > 0
    assert rendered.format == "png"
    assert rendered.dpi == 144


def test_render_page_fails_for_out_of_range_page(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=600, height=800)
    with source.open("wb") as f:
        writer.write(f)

    with pytest.raises(ValueError, match="out of range"):
        ProcessorService().render_page(str(source), page_number=2, output_path=str(tmp_path / "bad.png"))
