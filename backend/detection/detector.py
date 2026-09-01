"""Adaptador de inferencia YOLO para armas de fuego y armas blancas."""

from ultralytics import YOLO

CLASS_ALIASES = {
    "firearm": {"firearm", "gun", "guns", "pistol", "handgun", "rifle", "weapon"},
    "knife": {"knife", "knives", "machete", "blade"},
}


class WeaponDetector:
    def __init__(self, model_path: str, confidence: float = 0.70):
        self.model = YOLO(model_path)
        self.model.set_classes(["gun", "knife"])
        self.confidence = confidence

    def detect(self, frame) -> list[dict]:
        result = self.model.predict(frame, conf=self.confidence, verbose=False)[0]
        detections = []
        for box in result.boxes:
            confidence = float(box.conf[0])
            class_id = int(box.cls[0])
            source_label = str(result.names[class_id]).lower().strip()
            weapon_class = self._normalize_class(source_label)
            if weapon_class is None or confidence < self.confidence:
                continue
            detections.append(
                {
                    "weapon_class": weapon_class,
                    "confidence": confidence,
                    "bbox": [int(value) for value in box.xyxy[0].tolist()],
                }
            )
        return detections

    @staticmethod
    def _normalize_class(source_label: str) -> str | None:
        for weapon_class, aliases in CLASS_ALIASES.items():
            if source_label in aliases:
                return weapon_class
        return None
