"""Seguimiento de confirmación de detecciones de arma en frames consecutivos.

Antes de considerar una detección de arma como candidata a incidencia, se
exige que aparezca en varios frames consecutivos (RF-1). Tras confirmar una
detección, se aplica un enfriamiento antes de aceptar un nuevo seguimiento
(RF-3), para no reaccionar de inmediato a la misma arma que sigue en cámara.
"""

import time
from dataclasses import dataclass


@dataclass
class ConfirmedIncident:
    """Detección confirmada tras completar los frames consecutivos exigidos.

    Contiene el frame y la detección del último (RF-1.4) de esos frames,
    que es lo que se usa como evidencia en el resto del flujo.
    """

    frame: object
    detection: dict


class IncidentConfirmationTracker:
    """Máquina de estados en memoria: cuenta detecciones de `weapon`
    estrictamente consecutivas y aplica el enfriamiento posterior a cada
    confirmación. No persiste nada ni depende de un hilo propio: se invoca
    una vez por frame procesado por el pipeline.
    """

    def __init__(self, confirmation_frames: int, cooldown_seconds: float):
        self.confirmation_frames = confirmation_frames
        self.cooldown_seconds = cooldown_seconds
        self._consecutive_count = 0
        self._last_frame = None
        self._last_detection: dict | None = None
        self._cooldown_until = 0.0

    def observe(self, frame, detections: list[dict]) -> ConfirmedIncident | None:
        """Procesa un frame ya analizado por YOLO. Devuelve un
        `ConfirmedIncident` solo en el frame donde se completan
        `confirmation_frames` detecciones de arma consecutivas; en
        cualquier otro caso (sin detección, en enfriamiento, o seguimiento
        aún incompleto) devuelve `None`.
        """
        now = time.monotonic()
        if now < self._cooldown_until:
            # RF-3.2: en enfriamiento, se ignora cualquier detección.
            return None

        best_detection = self._best_weapon_detection(detections)
        if best_detection is None:
            # RF-1.3: un frame sin detección reinicia el seguimiento.
            self._reset_tracking()
            return None

        self._consecutive_count += 1
        self._last_frame = frame
        self._last_detection = best_detection

        if self._consecutive_count < self.confirmation_frames:
            return None

        # RF-1.4: se confirma con los datos del último frame de la secuencia.
        confirmed = ConfirmedIncident(frame=self._last_frame, detection=self._last_detection)
        # RF-3.1: arranca el enfriamiento antes de limpiar el seguimiento.
        self._cooldown_until = now + self.cooldown_seconds
        self._reset_tracking()
        return confirmed

    def reset(self) -> None:
        """Descarta cualquier seguimiento en curso sin registrar nada
        (RF-1.5), por ejemplo al detener o cambiar la fuente de video
        activa. No cancela un enfriamiento ya activo.
        """
        self._reset_tracking()

    def _reset_tracking(self) -> None:
        self._consecutive_count = 0
        self._last_frame = None
        self._last_detection = None

    @staticmethod
    def _best_weapon_detection(detections: list[dict]) -> dict | None:
        best = None
        for detection in detections:
            if detection.get("weapon_class") != "weapon":
                continue
            if best is None or detection["confidence"] > best["confidence"]:
                best = detection
        return best
