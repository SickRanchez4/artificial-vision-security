# Plan técnico — Spec 002: video source

Plan de implementación de `_sdd/specs/spec-002-video-source/spec.md`. Respeta la
constitución: stack fijo (Flask, Vue, YOLO ya implementado), lógica de fuentes
de video solo en backend salvo la captura de cámara (API nativa del navegador,
sin llamar a YOLO ni OpenAI desde el frontend), **sin tests automatizados**:
toda verificación queda a cargo del desarrollador mediante el protocolo manual
de la sección 7 (constitución, principio 4), identificadores en inglés y
textos en español.

---

## 1. Estructura de módulos

```
backend/
  streaming/
    video_source.py        # Puerto VideoSourcePort (ABC): start(), stop(),
                            #   onFrame(callback)                              → RF-4
    sources/
      file_source.py        # FileVideoSource: valida .mp4/256 MB, guarda
                            #   temporalmente, lee y descarta al finalizar     → RF-2
      camera_source.py       # CameraVideoSource: recibe frames JPEG que el
                            #   navegador empuja por HTTP, sin cv2.VideoCapture → RF-3
      factory.py             # create_video_source(type, **params) — Factory
                            #   Method, sin contenedor de DI                    → RF-1, RF-5
    session_repository.py    # CRUD de la tabla video_sessions                  → RF-7, RF-8
    routes.py                # Endpoints de selección/estado/subida/frames     → RF-1, RF-2,
                            #                                                  RF-3, RF-5, RF-6
  detection/
    pipeline.py             # Se adapta para consumir onFrame(callback) en vez
                            #   de un read() por sondeo; el resto (detección,
                            #   eventos, overlay) no cambia                    → RF-4

frontend/
  src/
    services/
      videoCapture.js       # enumerateDevices, getUserMedia, captura de
                            #   frames por canvas y envío periódico al backend → RF-3
      api.js                 # Extiende con endpoints de fuente/subida/estado  → RF-1..RF-8
    views/
      StreamView.vue         # Selector de fuente (archivo/cámara), subida
                            #   con progreso, selector de cámara, píldora
                            #   de estado, reproductor con play/pause/seek
                            #   para archivo                                  → RF-1..RF-3, RF-6
```

- El frontend solo usa APIs nativas del navegador (`MediaDevices`, `<input
  type=file>`, `fetch`/`XMLHttpRequest`) y la API REST de Flask: ni YOLO ni
  OpenAI aparecen en `frontend/` (constitución, principio 3).
- El pipeline de inferencia (`detector.py`, `overlay.py`, `events/`) **no se
  modifica**; solo cambia cómo `pipeline.py` obtiene el frame de entrada.

## 2. Modelo de datos (SQLite)

Nueva tabla `video_sessions`, sin persistir el binario del video ni el stream
(sección "Datos persistidos" de la spec).

### Tabla `video_sessions` → RF-7, RF-8, sección "Datos persistidos"

| Columna       | Tipo                 | Notas                                              |
|---------------|----------------------|-----------------------------------------------------|
| `id`          | text PK (UUID)       | Identificador de la sesión de análisis              |
| `source_type` | text                 | `upload` \| `live`                                  |
| `source_ref`  | text nullable        | Nombre original del archivo (antes de descartarlo); `null` para `live` |
| `started_at`  | text (ISO 8601 UTC)  |                                                      |
| `ended_at`    | text nullable        | `null` mientras la sesión está activa               |
| `status`      | text                 | `active` \| `finished` \| `error`                   |
| `error_message` | text nullable      | Mensaje mostrado al usuario si `status = error` (RF-6) |

No se agrega tabla para el archivo `.mp4` ni para frames de cámara: se
descartan/no se persisten (RF-2.5, "Datos persistidos").

## 3. Contratos de la app

### 3.1 API REST — selección y ciclo de vida de la fuente

| Método/Ruta | Entrada | Salida | RF |
|---|---|---|---|
| `POST /api/streaming/source` (archivo) | `multipart/form-data` con el `.mp4` | `202 {"session_id"}` mientras sube (progreso vía evento `progress` de `XMLHttpRequest` en el cliente) · `400 {"error": "Archivo no válido o mayor a 256 MB."}` | RF-1, RF-2.1–2.3 |
| `POST /api/streaming/source` | `{ "type": "live" }` | `202 {"session_id", "status": "connected"}` — el backend queda a la espera de frames | RF-1, RF-3.1 |
| `POST /api/streaming/camera-frame` | Cuerpo binario `image/jpeg` (una llamada por frame, 2–4 fps) | `204` · `409` si no hay sesión `live` activa | RF-3.1, RF-3.3 |
| `GET /api/streaming/source/status` | — | `200 {"status": "connecting"\|"connected"\|"error", "error_message"?}` | RF-6 |
| `DELETE /api/streaming/source` | — | `200` — detiene y libera la fuente activa (cierra `cv2.VideoCapture`, borra archivo temporal, cierra sesión con `ended_at`) | RF-5 |
| `GET /api/stream` (ya existente) | — | Sin cambios: sigue sirviendo MJPEG con los recuadros ya dibujados, ahora alimentado por cualquiera de las dos fuentes | RF-4 |

Toda ruta bajo `/api/streaming/*` requiere sesión de usuario (igual que el
resto de la API, spec-001 RF-1). El selector de cámaras (`enumerateDevices`)
es 100 % frontend y no requiere endpoint.

### 3.2 Contrato interno `VideoSourcePort` → RF-4

```python
class VideoSourcePort(ABC):
    def start(self) -> None: ...      # abre el recurso (cv2.VideoCapture o buffer de frames)
    def stop(self) -> None: ...       # libera el recurso; idempotente
    def on_frame(self, callback: Callable[[np.ndarray], None]) -> None: ...
```

- `FileVideoSource` corre un hilo interno que lee con `cv2.VideoCapture` y
  llama a `callback(frame)` por cada frame — mismo patrón que el
  `VideoSource` actual de spec-001, pero homogeneizado detrás del puerto.
- `CameraVideoSource` no abre ningún recurso propio: `on_frame` simplemente
  registra el callback, y el endpoint `POST /api/streaming/camera-frame`
  decodifica el JPEG recibido e invoca ese callback directamente. Así ambas
  fuentes exponen la misma interfaz aunque una sea "push" (cámara) y la otra
  "pull" (archivo).
- `pipeline.py` se suscribe una sola vez con `on_frame` al iniciar cada
  sesión; al cambiar de fuente (RF-5), primero se llama `stop()` sobre la
  fuente anterior y luego `start()`/`on_frame()` sobre la nueva.

## 4. Decisiones técnicas justificadas

1. **Puerto `VideoSourcePort` push (`on_frame`) en vez de pull (`read()`)** —
   la cámara solo puede entregar frames por empuje desde el navegador; para
   no tener dos formas distintas de alimentar el pipeline, se homogeneiza
   todo detrás de un callback. El archivo simula el push con un hilo lector
   interno reutilizando `cv2.VideoCapture` (ya usado en spec-001).
2. **Cámara: captura en el navegador + envío periódico de JPEG por HTTP**,
   sin WebRTC/servidor de señalización — cumple RF-3.1 con las APIs nativas
   del navegador (`getUserMedia`, `canvas.toBlob`) y sin añadir dependencias
   ni servicios (principio 1: simplicidad del stack). Suficiente para 2–4
   fps, que ya es la cadencia de inferencia real del pipeline (spec-001).
3. **Archivo `.mp4`: almacenamiento temporal en disco, no en SQLite** —
   distinto de las imágenes de eventos (que sí van a BD, spec-001): aquí el
   video se descarta al terminar (RF-2.5), así que guardarlo en BD sería
   trabajo innecesario; se usa un archivo temporal del sistema operativo que
   se borra explícitamente al finalizar o al cambiar de fuente (RF-5).
4. **`VideoSourceFactory` (Factory Method) en `sources/factory.py`** —
   sustituye el `if/elif` disperso por un único punto de creación según
   `type`, sin contenedor de inyección de dependencias (tal como sugiere la
   arquitectura de la spec).
5. **Sin reintento automático ante corte de conexión de cámara** — se marca
   la sesión como `error` con `error_message` y se detiene; coincide con
   "fuera de alcance" de la spec y con la constitución (no añadir
   complejidad no pedida).
6. **Tabla `video_sessions` mínima, sin guardar el binario ni el stream** —
   solo lo necesario para trazabilidad (RF-7, RF-8); coherente con el
   principio de simplicidad y con que archivo/cámara no se persisten como
   contenido, solo como metadata de sesión.
7. **Verificación manual a cargo del desarrollador, sin tests automatizados**
   (ver sección 7) — la constitución (principio 4) no admite tests
   automatizados; el desarrollador ejecuta y registra los casos manuales
   positivos, negativos y de error de cada RF antes de commitear a `main`,
   sin depender de ninguna suite ni framework de testing.

## 5. Dependencias previstas (trazadas a la spec)

| Dependencia | Justificación |
|---|---|
| `opencv-python` (ya en `requirements.txt`) | RF-2: lectura de video subido con `cv2.VideoCapture` |
| APIs nativas del navegador (`MediaDevices.getUserMedia`, `enumerateDevices`, `canvas`, `XMLHttpRequest`) | RF-3: sin librería adicional en el frontend |

No se requiere ninguna dependencia nueva fuera de las ya trazadas en
spec-001; cualquier adición futura exige actualizar primero la spec
(principio 1).

## 6. Cobertura de requisitos

| RF | Cubierto por |
|---|---|
| RF-1 | `sources/factory.py`, `routes.py` (`POST /api/streaming/source` con `type`), un solo `session_id` activo a la vez |
| RF-2.1–2.5 | `sources/file_source.py`, subida `multipart/form-data`, borrado del archivo temporal al finalizar |
| RF-3.1–3.4 | `videoCapture.js` (frontend, `getUserMedia`/`enumerateDevices`), `sources/camera_source.py`, `POST /api/streaming/camera-frame` |
| RF-4 | `video_source.py` (`VideoSourcePort`), adaptación de `detection/pipeline.py` a `on_frame` |
| RF-5 | `DELETE /api/streaming/source`, `stop()` de cada adaptador antes de crear el siguiente vía factory |
| RF-6 | Mensajes de error específicos por fuente en `routes.py` / `GET /api/streaming/source/status`, tabla `video_sessions.error_message` |
| RF-7 | Logging (`logging`, mismo patrón que `detection/pipeline.py`) en inicio/fin/error de cada sesión |
| RF-8 | Tabla `video_sessions.source_type`, incluso cuando el archivo se descarta |

## 7. Estrategia de verificación (manual, a cargo del desarrollador)

No se implementan pruebas automatizadas (constitución, principio 4): el único
desarrollador del proyecto es responsable de ejecutar esta verificación a
mano antes de cada commit que toque esta spec, y de dejar constancia en el
mensaje de commit de qué criterios se validaron. La siguiente tabla es la
guía de casos a recorrer, no un checklist automatizable:

| Caso | Resultado esperado | RF |
|---|---|---|
| Subir `.mp4` válido de tamaño normal | Progreso visible, reproducción con play/pause/seek, detección corriendo | RF-2.1, RF-2.3, RF-2.4 |
| Subir archivo > 256 MB o con extensión distinta | Rechazo antes de completar la subida, sin bloquear la UI | RF-2.2 |
| Finalizar análisis de archivo subido | Binario descartado; sesión queda con `source_type = upload` | RF-2.5 |
| Otorgar permiso de cámara con ≥ 2 dispositivos | Selector lista ambos; elegir uno no-default y confirmar que se usa | RF-3.1, RF-3.2 |
| Denegar permiso de cámara / sin cámaras disponibles | Error claro, lista vacía manejada sin romper la UI | RF-3.1, casos límite |
| Desconectar la cámara seleccionada en análisis | Un único mensaje de error, sin reintento | RF-3.4 |
| Cambiar de fuente (archivo → cámara) con análisis en curso | La fuente anterior libera su recurso (proceso/hilo/archivo temporal) antes de iniciar la nueva; solo una activa | RF-5 |
| Revisar logs del backend tras cada caso anterior | Cada sesión tiene entradas de inicio/fin/error | RF-7 |
| Consultar `video_sessions` tras cada caso anterior | `source_type` correcto (`upload`/`live`) y `status` final coherente | RF-8 |

Casos de seguridad crítica (falso negativo de detección) no aplican aquí:
esta spec no toca el pipeline de inferencia, solo la ingestión de frames.

