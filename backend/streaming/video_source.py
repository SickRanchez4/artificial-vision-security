"""Puerto común de las fuentes de video (RF-4)."""

from abc import ABC, abstractmethod
from collections.abc import Callable

import numpy as np


class VideoSourcePort(ABC):
    """Puerto común que deben implementar los adaptadores de fuente de video.

    Homogeneiza fuentes "pull" (archivo, que se leen con OpenCV) y "push"
    (cámara, que empuja frames desde el navegador) detrás de la misma
    interfaz: quien consume la fuente solo se suscribe con `on_frame`.
    """

    @abstractmethod
    def start(self) -> None:
        """Abre el recurso de la fuente (archivo, buffer de cámara, etc.)."""

    @abstractmethod
    def stop(self) -> None:
        """Libera el recurso de la fuente. Debe poder llamarse más de una vez."""

    @abstractmethod
    def on_frame(self, callback: Callable[[np.ndarray], None]) -> None:
        """Registra el callback que recibirá cada frame entregado por la fuente."""

