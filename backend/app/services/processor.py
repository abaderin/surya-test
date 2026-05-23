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
        with self.predictors.gpu_lock():
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

    def ocr(self, page_path: str, bbox_px: dict) -> dict:
        results = self.ocr_many(page_path, [bbox_px])
        if not results:
            return {"text": "", "raw_surya_ocr": []}
        return results[0]

    def ocr_many(self, page_path: str, bboxes_px: list[dict]) -> list[dict]:
        from PIL import Image

        predictor = self.predictors.get_recognition_predictor()
        normalized_boxes: list[tuple[int, int, int, int] | None] = []
        for bbox_px in bboxes_px:
            x1 = int(bbox_px["x"])
            y1 = int(bbox_px["y"])
            x2 = int(bbox_px["x"] + bbox_px["width"])
            y2 = int(bbox_px["y"] + bbox_px["height"])
            if x2 <= x1 or y2 <= y1:
                normalized_boxes.append(None)
                continue
            normalized_boxes.append((x1, y1, x2, y2))
        valid_boxes = [box for box in normalized_boxes if box is not None]
        if not valid_boxes:
            return [{"text": "", "raw_surya_ocr": []} for _ in bboxes_px]

        with Image.open(page_path) as image:
            rgb_image = image.convert("RGB")
        with self.predictors.gpu_lock():
            ocr_results = predictor(
                [rgb_image for _ in valid_boxes],
                bboxes=[[[x1, y1, x2, y2]] for x1, y1, x2, y2 in valid_boxes],
                sort_lines=True,
                math_mode=True,
            )
        extracted_valid_results: list[dict] = []
        for result in ocr_results or []:
            text_lines = getattr(result, "text_lines", []) or []
            text = "\n".join(
                str(getattr(line, "text", "")).strip()
                for line in text_lines
                if str(getattr(line, "text", "")).strip()
            )
            extracted_valid_results.append(
                {
                    "text": text,
                    "raw_surya_ocr": self._raw_surya_ocr(result),
                }
            )
        if len(extracted_valid_results) < len(valid_boxes):
            extracted_valid_results.extend(
                [{"text": "", "raw_surya_ocr": []} for _ in range(len(valid_boxes) - len(extracted_valid_results))]
            )

        output: list[dict] = []
        valid_index = 0
        for box in normalized_boxes:
            if box is None:
                output.append({"text": "", "raw_surya_ocr": []})
            else:
                output.append(extracted_valid_results[valid_index])
                valid_index += 1
        return output

    def _raw_surya_ocr(self, result: Any) -> Any:
        if hasattr(result, "model_dump"):
            dumped = result.model_dump(mode="json")
            return self._to_json_compatible(dumped)
        return self._to_json_compatible(result)

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
