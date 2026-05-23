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


def test_layout_many_batches_images_in_single_predictor_call(monkeypatch: pytest.MonkeyPatch) -> None:
    first_box = SimpleNamespace(
        bbox=[0.0, 0.0, 20.0, 10.0],
        polygon=[[0.0, 0.0], [20.0, 0.0], [20.0, 10.0], [0.0, 10.0]],
        label="PageHeader",
        position=0,
        top_k={"PageHeader": 0.8},
        confidence=0.8,
    )
    second_box = SimpleNamespace(
        bbox=[3.0, 4.0, 30.0, 14.0],
        polygon=[[3.0, 4.0], [30.0, 4.0], [30.0, 14.0], [3.0, 14.0]],
        label="Text",
        position=0,
        top_k={"Text": 0.9},
        confidence=0.9,
    )
    fake_results = [SimpleNamespace(bboxes=[first_box]), SimpleNamespace(bboxes=[second_box])]

    class FakeImage:
        def __init__(self, size: tuple[int, int]) -> None:
            self.size = size

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
            if path == "/tmp/one.png":
                return FakeImage((120, 200))
            assert path == "/tmp/two.png"
            return FakeImage((140, 220))

    class FakePredictor:
        def __call__(self, images: list[FakeImage]) -> list[SimpleNamespace]:
            assert len(images) == 2
            assert images[0].size == (120, 200)
            assert images[1].size == (140, 220)
            return fake_results

    monkeypatch.setitem(sys.modules, "PIL", SimpleNamespace(Image=FakePILImageModule))
    fake_predictors = SimpleNamespace(get_layout_predictor=lambda: FakePredictor())
    p = ProcessorService(predictors=fake_predictors)

    blocks_batch = p.layout_many([("/tmp/one.png", 120, 200), ("/tmp/two.png", 140, 220)])

    assert len(blocks_batch) == 2
    assert blocks_batch[0][0].block_type == "PageHeader"
    assert blocks_batch[1][0].block_type == "Text"


def test_detection_converts_surya_boxes_with_clipping_and_polygon(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_box = SimpleNamespace(
        bbox=[-10.0, 8.0, 150.0, 52.0],
        polygon=[[0.0, 10.0], [150.0, 8.0], [150.0, 52.0], [0.0, 50.0]],
        confidence=0.88,
        model_dump=lambda mode="json": {"bbox": [-10.0, 8.0, 150.0, 52.0], "confidence": 0.88},
    )
    fake_result = SimpleNamespace(bboxes=[fake_box])

    class FakeImage:
        size = (120, 200)

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
            return [fake_result]

    monkeypatch.setitem(sys.modules, "PIL", SimpleNamespace(Image=FakePILImageModule))
    fake_predictors = SimpleNamespace(get_detection_predictor=lambda: FakePredictor())
    p = ProcessorService(predictors=fake_predictors)

    detections = p.detection("/tmp/page.png", width=120, height=200)

    assert len(detections) == 1
    assert detections[0].bbox_px == {"x": 0, "y": 8, "width": 120, "height": 44}
    assert detections[0].bbox_norm == {"x": 0.0, "y": 0.04, "width": 1.0, "height": 0.22}
    assert detections[0].polygon_px == {
        "points": [
            {"x": 0.0, "y": 10.0},
            {"x": 150.0, "y": 8.0},
            {"x": 150.0, "y": 52.0},
            {"x": 0.0, "y": 50.0},
        ]
    }
    assert detections[0].confidence == 0.88
    assert detections[0].raw["confidence"] == 0.88


def test_ocr_page_extracts_lines_from_recognition_result(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_line1 = SimpleNamespace(
        text="Hello",
        bbox=[10, 20, 40, 60],
        polygon=[[10, 20], [40, 20], [40, 60], [10, 60]],
        confidence=0.9,
        model_dump=lambda mode="json": {"text": "Hello", "bbox": [10, 20, 40, 60]},
    )
    fake_line2 = SimpleNamespace(
        text="World",
        bbox=[100, 200, 170, 240],
        polygon=[[100, 200], [170, 200], [170, 240], [100, 240]],
        confidence=0.8,
        model_dump=lambda mode="json": {"text": "World", "bbox": [100, 200, 170, 240]},
    )
    fake_ocr_result = SimpleNamespace(text_lines=[fake_line1, fake_line2])
    fake_det_predictor = object()

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
        def __call__(self, images, det_predictor, sort_lines, math_mode):
            assert len(images) == 1
            assert det_predictor is fake_det_predictor
            assert sort_lines is True
            assert math_mode is True
            return [fake_ocr_result]

    monkeypatch.setitem(sys.modules, "PIL", SimpleNamespace(Image=FakePILImageModule))
    fake_predictors = SimpleNamespace(
        get_recognition_predictor=lambda: FakePredictor(),
        get_detection_predictor=lambda: fake_det_predictor,
        gpu_lock=lambda: nullcontext(),
    )
    p = ProcessorService(predictors=fake_predictors)

    results = p.ocr_page("/tmp/page.png")

    assert len(results) == 2
    assert results[0]["text"] == "Hello"
    assert results[0]["bbox_px"] == {"x": 10, "y": 20, "width": 30, "height": 40}
    assert results[1]["text"] == "World"
    assert results[1]["raw_surya_ocr"]["text"] == "World"


def test_ocr_page_uses_polygon_when_bbox_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_line = SimpleNamespace(
        text="First",
        bbox=None,
        polygon=[[10, 20], [30, 20], [30, 50], [10, 50]],
        confidence=0.95,
        model_dump=lambda mode="json": {"text": "First"},
    )
    fake_result = SimpleNamespace(text_lines=[fake_line])
    fake_det_predictor = object()

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
        def __call__(self, images, det_predictor, sort_lines, math_mode):
            assert len(images) == 1
            assert det_predictor is fake_det_predictor
            assert sort_lines is True
            assert math_mode is True
            return [fake_result]

    monkeypatch.setitem(sys.modules, "PIL", SimpleNamespace(Image=FakePILImageModule))
    fake_predictors = SimpleNamespace(
        get_recognition_predictor=lambda: FakePredictor(),
        get_detection_predictor=lambda: fake_det_predictor,
        gpu_lock=lambda: nullcontext(),
    )
    p = ProcessorService(predictors=fake_predictors)

    results = p.ocr_page("/tmp/page.png")

    assert len(results) == 1
    assert results[0]["text"] == "First"
    assert results[0]["bbox_px"] == {"x": 10, "y": 20, "width": 20, "height": 30}


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
