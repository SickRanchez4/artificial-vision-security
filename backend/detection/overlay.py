"""Presentación de detecciones sobre los frames de video."""

import cv2

LABELS = {"weapon": "Arma", "person": "Persona"}
COLORS = {"weapon": (42, 62, 255), "person": (0, 200, 120)}


def draw_detections(frame, detections: list[dict]):
    rendered = frame.copy()
    for detection in detections:
        x1, y1, x2, y2 = detection["bbox"]
        weapon_class = detection["weapon_class"]
        label = LABELS[weapon_class]
        color = COLORS[weapon_class]
        cv2.rectangle(rendered, (x1, y1), (x2, y2), color, 3)
        cv2.rectangle(rendered, (x1, max(0, y1 - 32)), (x2, y1), color, -1)
        cv2.putText(
            rendered,
            label,
            (x1 + 6, max(22, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
    return rendered


def create_idle_frame():
    """Frame mostrado mientras no hay ninguna fuente de video activa (RF-6)."""
    import numpy as np

    frame = np.full((720, 1280, 3), (24, 17, 7), dtype=np.uint8)
    cv2.putText(
        frame,
        "SIN FUENTE DE VIDEO ACTIVA",
        (250, 360),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.6,
        (190, 210, 225),
        3,
        cv2.LINE_AA,
    )
    return frame

