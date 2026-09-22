"""Adaptador de inferencia YOLO para armas de fuego y armas blancas."""

import torch
from ultralytics import YOLO

CLASS_ALIASES = {
    "weapon": {"weapon"},
    "person": {"person"},
}


class WeaponDetector:
    def __init__(self, model_path: str, weapon_confidence: float = 0.30, person_confidence: float = 0.30):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = YOLO(model_path)
        self.model.to(self.device)
        self.confidence_by_class = {"weapon": weapon_confidence, "person": person_confidence}
        # El modelo filtra con el umbral más bajo de las dos clases; el
        # filtro fino por clase se aplica después, en detect().
        self._predict_confidence = min(weapon_confidence, person_confidence)

    def detect(self, frame) -> list[dict]:
        result = self.model.predict(frame, conf=self._predict_confidence, verbose=False)[0]
        detections = []
        for box in result.boxes:
            confidence = float(box.conf[0])
            class_id = int(box.cls[0])
            source_label = str(result.names[class_id]).lower().strip()
            weapon_class = self._normalize_class(source_label)
            if weapon_class is None or confidence < self.confidence_by_class[weapon_class]:
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
