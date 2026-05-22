from __future__ import annotations

from dataclasses import dataclass
from typing import Any


VEHICLE_CLASSES = {"car", "truck", "bus", "motorcycle", "motorbike"}


@dataclass(frozen=True)
class Detection:
    label: str
    confidence: float
    x: float
    y: float
    width: float
    height: float


class VehicleDetector:
    """Thin optional YOLO adapter.

    The application works without heavy vision packages installed. When
    ultralytics is available, this adapter can load a YOLOv12-compatible model
    path from settings and convert vehicle detections into normalized boxes.
    """

    def __init__(self, model_path: str = "yolov12.pt", confidence: float = 0.35):
        self.model_path = model_path
        self.confidence = confidence
        self.model: Any | None = None
        self.error: str | None = None
        try:
            from ultralytics import YOLO

            self.model = YOLO(model_path)
        except Exception as exc:  # pragma: no cover - depends on optional runtime packages
            self.error = str(exc)

    @property
    def available(self) -> bool:
        return self.model is not None

    def detect(self, frame: Any) -> list[Detection]:
        if self.model is None:
            return []

        results = self.model(frame, conf=self.confidence, verbose=False)
        detections: list[Detection] = []
        for result in results:
            names = getattr(result, "names", {}) or {}
            for box in getattr(result, "boxes", []) or []:
                class_id = int(box.cls[0])
                label = str(names.get(class_id, class_id)).lower()
                if label not in VEHICLE_CLASSES:
                    continue
                x1, y1, x2, y2 = [float(value) for value in box.xyxy[0]]
                frame_height, frame_width = result.orig_shape[:2]
                detections.append(
                    Detection(
                        label=label,
                        confidence=float(box.conf[0]),
                        x=x1 / frame_width * 100,
                        y=y1 / frame_height * 100,
                        width=(x2 - x1) / frame_width * 100,
                        height=(y2 - y1) / frame_height * 100,
                    )
                )
        return detections
