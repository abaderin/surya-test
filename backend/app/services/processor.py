from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz
from pypdf import PdfReader

from app.core.settings import settings
from app.services.surya import SuryaPredictors


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

    def __init__(self, predictors: SuryaPredictors | None = None) -> None:
        self.predictors = predictors or SuryaPredictors(settings.storage_root_path / ".gpu-predictor.lock")

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

        predictor = self.predictors.get_layout_predictor()

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

    def ocr_page(self, page_path: str) -> list[dict]:
        from PIL import Image

        predictor = self.predictors.get_recognition_predictor()
        det_predictor = self.predictors.get_detection_predictor()
        with Image.open(page_path) as image:
            rgb_image = image.convert("RGB")
        ocr_results = predictor(
            [rgb_image],
            det_predictor=det_predictor,
            sort_lines=True,
            math_mode=True,
        )
        if not ocr_results:
            return []
        lines: list[dict] = []
        for result in ocr_results:
            text_lines = getattr(result, "text_lines", []) or []
            for text_line in text_lines:
                raw_text = str(getattr(text_line, "text", "")).strip()
                if not raw_text:
                    continue
                bbox = self._line_bbox(getattr(text_line, "bbox", None), getattr(text_line, "polygon", None))
                if bbox is None:
                    continue
                lines.append(
                    {
                        "text": raw_text,
                        "bbox_px": bbox,
                        "polygon_px": self._polygon_px(getattr(text_line, "polygon", None)),
                        "confidence": self._to_json_compatible(getattr(text_line, "confidence", None)),
                        "raw_surya_ocr": self._to_json_compatible(
                            text_line.model_dump(mode="json")
                            if hasattr(text_line, "model_dump")
                            else text_line
                        ),
                    }
                )
        return lines

    def _line_bbox(self, bbox: Any, polygon: Any) -> dict | None:
        if bbox and len(bbox) >= 4:
            x1, y1, x2, y2 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
            left, right = min(x1, x2), max(x1, x2)
            top, bottom = min(y1, y2), max(y1, y2)
            if right <= left or bottom <= top:
                return None
            return {
                "x": int(round(left)),
                "y": int(round(top)),
                "width": int(round(right - left)),
                "height": int(round(bottom - top)),
            }
        polygon_px = self._polygon_px(polygon)
        if not polygon_px:
            return None
        points = polygon_px["points"]
        xs = [point["x"] for point in points]
        ys = [point["y"] for point in points]
        left = min(xs)
        right = max(xs)
        top = min(ys)
        bottom = max(ys)
        if right <= left or bottom <= top:
            return None
        return {
            "x": int(round(left)),
            "y": int(round(top)),
            "width": int(round(right - left)),
            "height": int(round(bottom - top)),
        }

    def image_extraction(self, page_path: str, bbox_px: dict, output_path: str) -> dict:
        from PIL import Image

        x1 = int(bbox_px["x"])
        y1 = int(bbox_px["y"])
        x2 = int(bbox_px["x"] + bbox_px["width"])
        y2 = int(bbox_px["y"] + bbox_px["height"])
        if x2 <= x1 or y2 <= y1:
            raise ValueError("invalid bbox for image extraction")

        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(page_path) as image:
            rgb_image = image.convert("RGB")
            width, height = rgb_image.size
            left = max(0, min(width, x1))
            top = max(0, min(height, y1))
            right = max(0, min(width, x2))
            bottom = max(0, min(height, y2))
            if right <= left or bottom <= top:
                raise ValueError("bbox is outside image bounds")
            cropped = rgb_image.crop((left, top, right, bottom))
            cropped.save(target, format="PNG")
            return {"width_px": int(cropped.width), "height_px": int(cropped.height), "format": "png"}
