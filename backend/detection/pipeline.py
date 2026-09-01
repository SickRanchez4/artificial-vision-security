"""Pipeline continuo de video, detección, persistencia y notificación."""

import logging
import threading
import time
from datetime import datetime, timezone
from uuid import uuid4

import cv2

from backend.detection.detector import WeaponDetector
from backend.detection.overlay import create_offline_frame, draw_detections
from backend.events.repository import create_event, has_recent_event
from backend.integrations.n8n_client import send_event_for_analysis
from backend.streaming.video_source import VideoSource

logger = logging.getLogger(__name__)


class DetectionPipeline:
    def __init__(self, app):
        self.app = app
        self.source = VideoSource(app.config["VIDEO_SOURCE_PATH"])
        self.detector = None
        self.latest_frame = self._encode(create_offline_frame())
        self.camera_online = False
        self._last_events = {}
        self._condition = threading.Condition()
        self._thread = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="detection-pipeline")
        self._thread.start()

    def wait_for_frame(self, timeout: float = 2.0) -> tuple[bytes, bool]:
        with self._condition:
            self._condition.wait(timeout=timeout)
            return self.latest_frame, self.camera_online

    def _run(self) -> None:
        interval = 1 / max(self.app.config["DETECTION_FPS"], 0.5)
        with self.app.app_context():
            while True:
                started_at = time.monotonic()
                frame = self.source.read()
                if frame is None:
                    self._publish(create_offline_frame(), False)
                    time.sleep(1)
                    continue

                detections = self._detect(frame)
                self._create_events(frame, detections)
                self._publish(draw_detections(frame, detections), True)
                time.sleep(max(0, interval - (time.monotonic() - started_at)))

    def _detect(self, frame) -> list[dict]:
        try:
            if self.detector is None:
                self.detector = WeaponDetector(
                    self.app.config["YOLO_MODEL_PATH"],
                    self.app.config["DETECTION_CONFIDENCE"],
                )
            return self.detector.detect(frame)
        except Exception:
            logger.exception("No se pudo ejecutar la detección YOLO.")
            return []

    def _create_events(self, frame, detections: list[dict]) -> None:
        best_by_class = {}
        for detection in detections:
            weapon_class = detection["weapon_class"]
            current = best_by_class.get(weapon_class)
            if current is None or detection["confidence"] > current["confidence"]:
                best_by_class[weapon_class] = detection

        for weapon_class, detection in best_by_class.items():
            if self._is_in_cooldown(weapon_class):
                continue
            success, encoded = cv2.imencode(".jpg", frame)
            if not success:
                continue
            event_id = uuid4()
            detected_at = datetime.now(timezone.utc)
            create_event(event_id, detected_at, weapon_class, detection["confidence"], encoded.tobytes())
            self._last_events[weapon_class] = time.monotonic()
            threading.Thread(
                target=self._send_event,
                args=(str(event_id), detected_at, detection, encoded.tobytes()),
                daemon=True,
            ).start()

    def _is_in_cooldown(self, weapon_class: str) -> bool:
        cooldown = self.app.config["DETECTION_COOLDOWN_SECONDS"]
        last_event = self._last_events.get(weapon_class)
        if last_event is not None and time.monotonic() - last_event < cooldown:
            return True
        return has_recent_event(weapon_class, cooldown)

    def _send_event(self, event_id: str, detected_at: datetime, detection: dict, image: bytes) -> None:
        with self.app.app_context():
            send_event_for_analysis(event_id, detected_at, detection, image)

    def _publish(self, frame, camera_online: bool) -> None:
        encoded = self._encode(frame)
        with self._condition:
            self.latest_frame = encoded
            self.camera_online = camera_online
            self._condition.notify_all()

    @staticmethod
    def _encode(frame) -> bytes:
        success, encoded = cv2.imencode(".jpg", frame)
        return encoded.tobytes() if success else b""