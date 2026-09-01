"""Presentación de detecciones sobre los frames de video."""

import cv2

LABELS = {"firearm": "Arma de fuego", "knife": "Arma blanca"}


def draw_detections(frame, detections: list[dict]):
    rendered = frame.copy()
    for detection in detections:
        x1, y1, x2, y2 = detection["bbox"]
        label = LABELS[detection["weapon_class"]]
        confidence = round(detection["confidence"] * 100)
        text = f"{label} · {confidence}%"
        cv2.rectangle(rendered, (x1, y1), (x2, y2), (42, 62, 255), 3)
        cv2.rectangle(rendered, (x1, max(0, y1 - 32)), (x2, y1), (42, 62, 255), -1)
        cv2.putText(
            rendered,
            text,
            (x1 + 6, max(22, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
    return rendered


def create_offline_frame():
    import numpy as np

    frame = np.full((720, 1280, 3), (24, 17, 7), dtype=np.uint8)
    cv2.putText(
        frame,
        "CAMARA SIN SENAL",
        (390, 360),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.6,
        (190, 210, 225),
        3,
        cv2.LINE_AA,
    )
    return frame
