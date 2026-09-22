"""Adaptador de fuente de video para la cámara del navegador (RF-3).

A diferencia de `FileVideoSource`, esta fuente no abre ningún recurso propio
en el backend: los frames llegan "empujados" desde el navegador (uno por
llamada a `POST /api/streaming/camera-frame`) y simplemente se reenvían al
callback registrado con `on_frame`.
"""

import logging
from collections.abc import Callable

import numpy as np

from backend.streaming.video_source import VideoSourcePort

logger = logging.getLogger(__name__)


class CameraVideoSource(VideoSourcePort):
    def __init__(self):
        self._frame_callback: Callable[[np.ndarray], None] | None = None
        self._active = False

    def start(self) -> None:
        self._active = True

    def stop(self) -> None:
        self._active = False

    def on_frame(self, callback: Callable[[np.ndarray], None]) -> None:
        self._frame_callback = callback

    @property
    def is_active(self) -> bool:
        return self._active

    def push_frame(self, frame: np.ndarray) -> bool:
        """Entrega un frame recibido del navegador al callback registrado.

        Devuelve `False` si la fuente no está activa (por ejemplo, ya se
        detuvo o cambió de fuente), para que el endpoint responda `409`.
        """
        if not self._active or self._frame_callback is None:
            return False
        self._frame_callback(frame)
        return True
