from pathlib import Path
from types import SimpleNamespace
import sys
from contextlib import nullcontext

import pytest
from pypdf import PdfWriter

from app.services.processor import ProcessorService


def test_layout_converts_surya_boxes_with_clipping_and_polygon(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_box = SimpleNamespace(
        bbox=[-20.0, 15.0, 1400.0, 200.0],
        polygon=[[0.0, 15.0], [1200.0, 15.0], [1200.0, 200.0], [0.0, 200.0]],
        label="Text",
        position=0,
        top_k={"Text": 0.9},
        confidence=0.95,
    )
    fake_result = SimpleNamespace(bboxes=[fake_box])

    class FakeImage:
        size = (1200, 1600)

        def convert(self, mode: str) -> "FakeImage":
            assert mode == "RGB"
            return self

        def __enter__(self) -> "FakeImage":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    class FakePILImageModule:
        @staticmethod
        def open(path: str) -> FakeImage:
            assert path == "/tmp/page.png"
            return FakeImage()

    class FakePredictor:
        def __call__(self, images: list[FakeImage]) -> list[SimpleNamespace]:
            assert len(images) == 1
            assert images[0].size == (1200, 1600)
            return [fake_result]

    monkeypatch.setitem(sys.modules, "PIL", SimpleNamespace(Image=FakePILImageModule))
    fake_predictors = SimpleNamespace(
        get_layout_predictor=lambda: FakePredictor(),
        gpu_lock=lambda: nullcontext(),
    )
    p = ProcessorService(predictors=fake_predictors)

    blocks = p.layout("/tmp/page.png", width=1200, height=1600)

    assert len(blocks) == 1
    assert blocks[0].block_type == "Text"
    assert blocks[0].bbox_px == {"x": 0, "y": 15, "width": 1200, "height": 185}
    assert blocks[0].bbox_norm == {"x": 0.0, "y": 0.009375, "width": 1.0, "height": 0.115625}
    assert blocks[0].polygon_px == {
        "points": [
            {"x": 0.0, "y": 15.0},
            {"x": 1200.0, "y": 15.0},
            {"x": 1200.0, "y": 200.0},
            {"x": 0.0, "y": 200.0},
        ]
    }
    assert blocks[0].confidence == 0.95
    assert blocks[0].raw["label"] == "Text"


def test_ocr_extracts_text_from_recognition_result(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_line1 = SimpleNamespace(text="Hello")
    fake_line2 = SimpleNamespace(text="World")
    fake_ocr_result = SimpleNamespace(
        text_lines=[fake_line1, fake_line2],
        model_dump=lambda mode="json": {"text_lines": [{"text": "Hello"}, {"text": "World"}]},
    )

    class FakeImage:
        def convert(self, mode: str) -> "FakeImage":
            assert mode == "RGB"
            return self

        def __enter__(self) -> "FakeImage":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    class FakePILImageModule:
        @staticmethod
        def open(path: str) -> FakeImage:
            assert path == "/tmp/page.png"
            return FakeImage()

    class FakePredictor:
        def __call__(self, images, bboxes, sort_lines, math_mode):
            assert len(images) == 1
            assert bboxes == [[[10, 20, 40, 60]]]
            assert sort_lines is True
            assert math_mode is True
            return [fake_ocr_result]

    monkeypatch.setitem(sys.modules, "PIL", SimpleNamespace(Image=FakePILImageModule))
    fake_predictors = SimpleNamespace(
        get_recognition_predictor=lambda: FakePredictor(),
        gpu_lock=lambda: nullcontext(),
    )
    p = ProcessorService(predictors=fake_predictors)

    result = p.ocr("/tmp/page.png", {"x": 10, "y": 20, "width": 30, "height": 40})

    assert result["text"] == "Hello\nWorld"
    assert result["raw_surya_ocr"]["text_lines"][0]["text"] == "Hello"


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


def test_image_extraction_crops_image_and_returns_dimensions(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    class FakeCrop:
        width = 30
        height = 25

        def save(self, path: Path, format: str) -> None:
            calls["save_path"] = str(path)
            calls["save_format"] = format

    class FakeImage:
        size = (100, 80)

        def convert(self, mode: str) -> "FakeImage":
            assert mode == "RGB"
            return self

        def crop(self, box: tuple[int, int, int, int]) -> FakeCrop:
            calls["crop_box"] = box
            return FakeCrop()

        def __enter__(self) -> "FakeImage":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    class FakePILImageModule:
        @staticmethod
        def open(path: str) -> FakeImage:
            assert path == "/tmp/page.png"
            return FakeImage()

    monkeypatch.setitem(sys.modules, "PIL", SimpleNamespace(Image=FakePILImageModule))

    result = ProcessorService().image_extraction(
        "/tmp/page.png",
        {"x": 10, "y": 20, "width": 30, "height": 25},
        "/tmp/crop.png",
    )

    assert calls["crop_box"] == (10, 20, 40, 45)
    assert calls["save_path"] == "/tmp/crop.png"
    assert calls["save_format"] == "PNG"
    assert result == {"width_px": 30, "height_px": 25, "format": "png"}
