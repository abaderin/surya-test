from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz
from pypdf import PdfReader


@dataclass
class LayoutBlock:
    block_type: str
    bbox_px: dict
    bbox_norm: dict
    polygon_px: dict | None
    confidence: float
    raw: dict


@dataclass
class RenderedPage:
    width_px: int
    height_px: int
    dpi: int
    format: str


class ProcessorService:
    """Runtime adapter boundary for PDF/page processing."""

    def __init__(self) -> None:
        self._layout_predictor: Any | None = None
        self._recognition_predictor: Any | None = None

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
        from PIL import Image

        predictor = self._get_layout_predictor()

        with Image.open(page_path) as image:
            rgb_image = image.convert("RGB")
        layout_results = predictor([rgb_image])
        if not layout_results:
            return []

        result = layout_results[0]
        boxes = getattr(result, "bboxes", []) or []
        blocks: list[LayoutBlock] = []
        for box in boxes:
            bbox = getattr(box, "bbox", None)
            if not bbox or len(bbox) < 4:
                continue

            x1, y1, x2, y2 = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
            left = max(0.0, min(float(width), x1))
            top = max(0.0, min(float(height), y1))
            right = max(0.0, min(float(width), x2))
            bottom = max(0.0, min(float(height), y2))
            if right < left:
                left, right = right, left
            if bottom < top:
                top, bottom = bottom, top

            bbox_width = max(0.0, right - left)
            bbox_height = max(0.0, bottom - top)
            block_type = str(getattr(box, "label", "unknown"))
            polygon = self._polygon_px(getattr(box, "polygon", None))
            confidence = float(getattr(box, "confidence", 0.0))

            blocks.append(
                LayoutBlock(
                    block_type=block_type,
                    bbox_px={
                        "x": int(round(left)),
                        "y": int(round(top)),
                        "width": int(round(bbox_width)),
                        "height": int(round(bbox_height)),
                    },
                    bbox_norm={
                        "x": round(left / width, 6),
                        "y": round(top / height, 6),
                        "width": round(bbox_width / width, 6),
                        "height": round(bbox_height / height, 6),
                    },
                    polygon_px=polygon,
                    confidence=confidence,
                    raw=self._raw_surya_block(box),
                )
            )
        return blocks

    def _get_layout_predictor(self) -> Any:
        if self._layout_predictor is not None:
            return self._layout_predictor
        from surya.foundation import FoundationPredictor
        from surya.layout import LayoutPredictor
        from surya.settings import settings as surya_settings

        foundation = FoundationPredictor(checkpoint=surya_settings.LAYOUT_MODEL_CHECKPOINT)
        self._layout_predictor = LayoutPredictor(foundation)
        return self._layout_predictor

    def _raw_surya_block(self, box: Any) -> dict:
        if hasattr(box, "model_dump"):
            dumped = box.model_dump(mode="json")
            if isinstance(dumped, dict):
                return dumped
        return {
            "bbox": self._to_json_compatible(getattr(box, "bbox", None)),
            "polygon": self._to_json_compatible(getattr(box, "polygon", None)),
            "label": self._to_json_compatible(getattr(box, "label", None)),
            "position": self._to_json_compatible(getattr(box, "position", None)),
            "top_k": self._to_json_compatible(getattr(box, "top_k", None)),
            "confidence": self._to_json_compatible(getattr(box, "confidence", None)),
        }

    def _polygon_px(self, polygon: Any) -> dict | None:
        if not polygon:
            return None
        points: list[dict[str, float]] = []
        for point in polygon:
            if not point or len(point) < 2:
                continue
            points.append({"x": float(point[0]), "y": float(point[1])})
        if not points:
            return None
        return {"points": points}

    def _to_json_compatible(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(k): self._to_json_compatible(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._to_json_compatible(v) for v in value]
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)

    def ocr(self, page_path: str, bbox_px: dict) -> dict:
        from PIL import Image

        predictor = self._get_recognition_predictor()
        x1 = int(bbox_px["x"])
        y1 = int(bbox_px["y"])
        x2 = int(bbox_px["x"] + bbox_px["width"])
        y2 = int(bbox_px["y"] + bbox_px["height"])
        if x2 <= x1 or y2 <= y1:
            return {"text": "", "raw_surya_ocr": []}

        with Image.open(page_path) as image:
            rgb_image = image.convert("RGB")
        ocr_results = predictor(
            [rgb_image],
            bboxes=[[[x1, y1, x2, y2]]],
            sort_lines=True,
            math_mode=True,
        )
        if not ocr_results:
            return {"text": "", "raw_surya_ocr": []}

        result = ocr_results[0]
        text_lines = getattr(result, "text_lines", []) or []
        text = "\n".join(str(getattr(line, "text", "")).strip() for line in text_lines if str(getattr(line, "text", "")).strip())
        return {
            "text": text,
            "raw_surya_ocr": self._raw_surya_ocr(result),
        }

    def _get_recognition_predictor(self) -> Any:
        if self._recognition_predictor is not None:
            return self._recognition_predictor
        from surya.foundation import FoundationPredictor
        from surya.recognition import RecognitionPredictor
        from surya.settings import settings as surya_settings

        foundation = FoundationPredictor(checkpoint=surya_settings.RECOGNITION_MODEL_CHECKPOINT)
        self._recognition_predictor = RecognitionPredictor(foundation)
        return self._recognition_predictor

    def _raw_surya_ocr(self, result: Any) -> Any:
        if hasattr(result, "model_dump"):
            dumped = result.model_dump(mode="json")
            return self._to_json_compatible(dumped)
        return self._to_json_compatible(result)

    def image_extraction(self, block_type: str) -> dict:
        if block_type == "image":
            return {"image_note": "image extraction placeholder"}
        return {}
