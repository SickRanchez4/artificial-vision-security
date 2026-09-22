"""Adaptador de fuente de video para archivos .mp4 subidos por el usuario."""

import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path

import cv2
import numpy as np

from backend.streaming.video_source import VideoSourcePort

logger = logging.getLogger(__name__)


class FileVideoSource(VideoSourcePort):
    """Lee una sola vez (sin bucle) un archivo de video subido y notifica su fin.

    A diferencia del `VideoSource` de demo (spec-001), que reproduce en bucle,
    el archivo subido se analiza una única vez: al llegar al final se invoca
    el callback de fin registrado con `on_end`, para que quien orquesta la
    sesión (routes.py) descarte el archivo y cierre la sesión (RF-2.5).
    """

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self._capture: cv2.VideoCapture | None = None
        self._thread: threading.Thread | None = None
        self._frame_callback: Callable[[np.ndarray], None] | None = None
        self._end_callback: Callable[[], None] | None = None
        self._error_callback: Callable[[str], None] | None = None
        self._stop_requested = threading.Event()

    def on_frame(self, callback: Callable[[np.ndarray], None]) -> None:
        self._frame_callback = callback

    def on_end(self, callback: Callable[[], None]) -> None:
        """Registra un callback invocado cuando el archivo termina por sí solo."""
        self._end_callback = callback

    def on_error(self, callback: Callable[[str], None]) -> None:
        """Registra un callback invocado si la lectura falla (archivo corrupto)."""
        self._error_callback = callback

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_requested.clear()
        self._capture = cv2.VideoCapture(str(self.file_path))
        if not self._capture.isOpened():
            self._capture = None
            raise RuntimeError("No se pudo abrir el archivo de video.")
        self._thread = threading.Thread(target=self._run, daemon=True, name="file-video-source")
        self._thread.start()

    def stop(self) -> None:
        self._stop_requested.set()
        current = self._thread
        if current is not None and current.is_alive() and threading.current_thread() is not current:
            current.join(timeout=2)
        self._release_capture()

    def _run(self) -> None:
        interval = 1 / self._get_fps()
        ended_naturally = False
        error_message = None
        try:
            while not self._stop_requested.is_set():
                started_at = time.monotonic()
                capture = self._capture
                success, frame = capture.read() if capture is not None else (False, None)
                if not success:
                    ended_naturally = True
                    break
                if self._frame_callback is not None:
                    self._frame_callback(frame)
                time.sleep(max(0, interval - (time.monotonic() - started_at)))
        except Exception:
            logger.exception("Error leyendo el archivo de video subido.")
            error_message = "El archivo de video está dañado o no se pudo leer."
        finally:
            self._release_capture()
            if error_message is not None and self._error_callback is not None:
                self._error_callback(error_message)
            elif ended_naturally and self._end_callback is not None:
                self._end_callback()

    def _get_fps(self, default: float = 25.0) -> float:
        if self._capture is None:
            return default
        fps = self._capture.get(cv2.CAP_PROP_FPS)
        return fps if fps and fps > 1 else default

    def _release_capture(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None
