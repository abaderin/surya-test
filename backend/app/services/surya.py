from pathlib import Path
from threading import Lock
from typing import Any
import contextlib
import fcntl


class SuryaPredictors:
    def __init__(self, lock_file: Path) -> None:
        self._layout_predictor: Any | None = None
        self._recognition_predictor: Any | None = None
        self._detection_predictor: Any | None = None
        self._layout_init_lock = Lock()
        self._recognition_init_lock = Lock()
        self._detection_init_lock = Lock()
        self._lock_file = lock_file

    def get_layout_predictor(self) -> Any:
        if self._layout_predictor is not None:
            return self._layout_predictor
        with self._layout_init_lock:
            if self._layout_predictor is None:
                from surya.foundation import FoundationPredictor
                from surya.layout import LayoutPredictor
                from surya.settings import settings as surya_settings

                foundation = FoundationPredictor(checkpoint=surya_settings.LAYOUT_MODEL_CHECKPOINT)
                self._layout_predictor = LayoutPredictor(foundation)
        return self._layout_predictor

    def get_recognition_predictor(self) -> Any:
        if self._recognition_predictor is not None:
            return self._recognition_predictor
        with self._recognition_init_lock:
            if self._recognition_predictor is None:
                from surya.foundation import FoundationPredictor
                from surya.recognition import RecognitionPredictor
                from surya.settings import settings as surya_settings

                foundation = FoundationPredictor(checkpoint=surya_settings.RECOGNITION_MODEL_CHECKPOINT)
                self._recognition_predictor = RecognitionPredictor(foundation)
        return self._recognition_predictor

    def get_detection_predictor(self) -> Any:
        if self._detection_predictor is not None:
            return self._detection_predictor
        with self._detection_init_lock:
            if self._detection_predictor is None:
                from surya.detection import DetectionPredictor
                from surya.settings import settings as surya_settings

                self._detection_predictor = DetectionPredictor(checkpoint=surya_settings.DETECTOR_MODEL_CHECKPOINT)
        return self._detection_predictor

    @contextlib.contextmanager
    def gpu_lock(self):
        self._lock_file.parent.mkdir(parents=True, exist_ok=True)
        with self._lock_file.open("a+") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
