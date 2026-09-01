"""Fuente de video pregrabado reproducido en bucle."""

from pathlib import Path
from threading import Lock

import cv2


class VideoSource:
    def __init__(self, source_path: str):
        self.source_path = Path(source_path).expanduser() if source_path else None
        self._capture = None
        self._lock = Lock()

    def read(self):
        with self._lock:
            if not self._ensure_open():
                return None

            success, frame = self._capture.read()
            if success:
                return frame

            self._capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            success, frame = self._capture.read()
            if success:
                return frame

            self._release()
            return None

    def close(self) -> None:
        with self._lock:
            self._release()

    def _ensure_open(self) -> bool:
        if self._capture is not None and self._capture.isOpened():
            return True
        if self.source_path is None or not self.source_path.is_file():
            return False
        self._capture = cv2.VideoCapture(str(self.source_path))
        return self._capture.isOpened()

    def _release(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None
