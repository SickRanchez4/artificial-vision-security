"""Pipeline de detección: procesa los frames entregados por la fuente activa."""

import logging
import threading
from datetime import datetime, timezone
from uuid import uuid4

import cv2

from backend.detection.detector import WeaponDetector
from backend.detection.overlay import create_idle_frame, draw_detections
from backend.events.repository import create_event
from backend.integrations.n8n_client import send_event_for_analysis
from backend.streaming.video_source import VideoSourcePort

logger = logging.getLogger(__name__)


class DetectionPipeline:
    """Consume frames de la fuente de video activa (archivo o cámara, RF-1) y
    ejecuta la detección YOLO sobre cada uno. Sin fuente activa no hay
    lectura ni publicación de frames nuevos: solo se muestra el frame de
    espera (RF-6).
    """

    def __init__(self, app):
        self.app = app
        self.detector = None
        self.latest_frame = self._encode(create_idle_frame())
        self.source_online = False
        self._condition = threading.Condition()
        self._active_source: VideoSourcePort | None = None

    def start(self) -> None:
        with self.app.app_context():
            self._warm_up_detector()

    def _warm_up_detector(self) -> None:
        try:
            self.detector = WeaponDetector(
                self.app.config["YOLO_MODEL_PATH"],
                self.app.config["DETECTION_CONFIDENCE_WEAPON"],
                self.app.config["DETECTION_CONFIDENCE_PERSON"],
            )
        except Exception:
            logger.exception("No se pudo precargar el modelo YOLO.")

    def wait_for_frame(self, timeout: float = 2.0) -> tuple[bytes, bool]:
        with self._condition:
            self._condition.wait(timeout=timeout)
            return self.latest_frame, self.source_online

    def set_active_source(self, source: VideoSourcePort) -> None:
        """Reemplaza la fuente activa (RF-1, RF-5) por una que empuja frames.

        Detiene y libera la fuente anterior (si la había) antes de
        suscribirse a la nueva; solo una fuente puede estar activa a la vez.
        """
        self.stop_active_source()
        source.on_frame(self._handle_pushed_frame)
        source.start()
        self._active_source = source

    def stop_active_source(self) -> None:
        """Detiene y libera la fuente activa, si existe (RF-5), y vuelve al
        frame de espera (RF-6)."""
        active = self._active_source
        self._active_source = None
        if active is not None:
            try:
                active.stop()
            except Exception:
                logger.exception("Error al detener la fuente de video activa.")
        self._publish(create_idle_frame(), False)

    def _handle_pushed_frame(self, frame) -> None:
        """Procesa un frame entregado por la fuente activa (RF-4)."""
        with self.app.app_context():
            detections = self._detect(frame)
            if not self.app.config.get("DEBUG_DISABLE_EVENTS"):
                try:
                    self._create_events(frame, detections)
                except Exception:
                    logger.exception("No se pudo registrar el evento de detección.")
            self._publish(draw_detections(frame, detections), True)

    def _detect(self, frame) -> list[dict]:
        try:
            if self.detector is None:
                self.detector = WeaponDetector(
                    self.app.config["YOLO_MODEL_PATH"],
                    self.app.config["DETECTION_CONFIDENCE_WEAPON"],
                    self.app.config["DETECTION_CONFIDENCE_PERSON"],
                )
            return self.detector.detect(frame)
        except Exception:
            logger.exception("No se pudo ejecutar la detección YOLO.")
            return []

    def _create_events(self, frame, detections: list[dict]) -> None:
        # Los eventos solo se generan para "weapon" (ver filtro abajo), por lo
        # que se usa su umbral específico, no el de "person".
        min_confidence = self.app.config["DETECTION_CONFIDENCE_WEAPON"]
        best_by_class = {}
        for detection in detections:
            weapon_class = detection["weapon_class"]
            if weapon_class != "weapon" or detection["confidence"] < min_confidence:
                continue
            current = best_by_class.get(weapon_class)
            if current is None or detection["confidence"] > current["confidence"]:
                best_by_class[weapon_class] = detection

        for weapon_class, detection in best_by_class.items():
            success, encoded = cv2.imencode(".jpg", frame)
            if not success:
                continue
            event_id = uuid4()
            detected_at = datetime.now(timezone.utc)
            create_event(event_id, detected_at, weapon_class, detection["confidence"], encoded.tobytes())
            threading.Thread(
                target=self._send_event,
                args=(str(event_id), detected_at, detection, encoded.tobytes()),
                daemon=True,
            ).start()

    def _send_event(self, event_id: str, detected_at: datetime, detection: dict, image: bytes) -> None:
        with self.app.app_context():
            send_event_for_analysis(event_id, detected_at, detection, image)

    def _publish(self, frame, source_online: bool) -> None:
        encoded = self._encode(frame)
        with self._condition:
            self.latest_frame = encoded
            self.source_online = source_online
            self._condition.notify_all()

    @staticmethod
    def _encode(frame) -> bytes:
        success, encoded = cv2.imencode(".jpg", frame)
        return encoded.tobytes() if success else b""
