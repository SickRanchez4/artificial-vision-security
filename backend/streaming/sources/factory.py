"""Factory Method para instanciar adaptadores de `VideoSourcePort` (RF-1, RF-5).

Evita un `if/elif` disperso en las rutas: quien necesita una fuente nueva
solo conoce el tipo (`upload` | `live`) y los parámetros propios de esa
fuente concreta. Sin contenedor de inyección de dependencias, tal como
sugiere la arquitectura de la spec.
"""

from backend.streaming.sources.camera_source import CameraVideoSource
from backend.streaming.sources.file_source import FileVideoSource
from backend.streaming.video_source import VideoSourcePort

SUPPORTED_SOURCE_TYPES = ("upload", "live")


def create_video_source(source_type: str, **params) -> VideoSourcePort:
    if source_type == "upload":
        return FileVideoSource(params["file_path"])
    if source_type == "live":
        return CameraVideoSource()
    raise ValueError(f"Tipo de fuente de video no soportado: {source_type!r}")
