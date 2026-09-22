"""Pipeline de detección: procesa los frames entregados por la fuente activa."""

import logging
import threading
from datetime import datetime, timezone
from uuid import uuid4

import cv2

from backend.detection.detector import WeaponDetector
from backend.detection.incident_tracker import IncidentConfirmationTracker
from backend.detection.overlay import create_idle_frame, draw_detections
from backend.events.repository import create_event
from backend.integrations.n8n_client import verify_incident
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
        self._incident_tracker = IncidentConfirmationTracker(
            app.config["CONFIRMATION_FRAMES"],
            app.config["INCIDENT_COOLDOWN_SECONDS"],
        )

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
        # RF-1.5: un seguimiento de confirmación en curso no sobrevive al
        # cambio o detención de la fuente activa.
        self._incident_tracker.reset()
        self._publish(create_idle_frame(), False)

    def _handle_pushed_frame(self, frame) -> None:
        """Procesa un frame entregado por la fuente activa (RF-4)."""
        with self.app.app_context():
            detections = self._detect(frame)
            if not self.app.config.get("DEBUG_DISABLE_EVENTS"):
                try:
                    self._track_incident(frame, detections)
                except Exception:
                    logger.exception("No se pudo procesar el seguimiento de incidencia.")
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

    def _track_incident(self, frame, detections: list[dict]) -> None:
        """Alimenta el seguimiento de confirmación (RF-1) con el frame
        actual; si se confirman los frames consecutivos exigidos, lanza en
        un hilo la verificación con n8n y el registro del evento (RF-2)."""
        confirmed = self._incident_tracker.observe(frame, detections)
        if confirmed is None:
            return

        success, encoded = cv2.imencode(".jpg", confirmed.frame)
        if not success:
            logger.error("No se pudo codificar el frame confirmado como JPEG.")
            return

        event_id = uuid4()
        detected_at = datetime.now(timezone.utc)
        threading.Thread(
            target=self._verify_and_register_incident,
            args=(event_id, detected_at, confirmed.detection, encoded.tobytes()),
            daemon=True,
        ).start()

    def _verify_and_register_incident(
        self, event_id, detected_at: datetime, detection: dict, image: bytes
    ) -> None:
        """Verifica la detección confirmada con n8n (RF-2.1, RF-2.2) y
        registra el evento según el resultado (RF-2.3–RF-2.5)."""
        with self.app.app_context():
            result = verify_incident(str(event_id), detected_at, detection, image)
            if result is None:
                # RF-2.5: sin respuesta válida de n8n, se registra igual
                # como análisis fallido, con la imagen pero sin reporte.
                create_event(
                    event_id,
                    detected_at,
                    detection["weapon_class"],
                    detection["confidence"],
                    image,
                    analysis_status="failed",
                )
                return
            if not result["is_real_incident"]:
                # RF-2.4: descartado, no se registra nada.
                return
            # RF-2.3: incidencia real confirmada por n8n.
            create_event(
                event_id,
                detected_at,
                detection["weapon_class"],
                detection["confidence"],
                image,
                analysis_status="done",
                report_text=result.get("report_text"),
                suspects_number=result.get("suspects_number"),
                suspects_description=result.get("suspects_description"),
            )

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
