# Tareas — Spec 002: video source

Derivadas de `spec.md` y `plan.md`. Orden de dependencia: cada tarea asume
completadas las anteriores. Sin tests automatizados: verificación manual a
cargo del desarrollador (constitución, principio 4; plan, sección 7).

## Fase 0 — Puerto y modelo de datos

- [x] **T-01 · Puerto `VideoSourcePort`** — Crear
  `backend/streaming/video_source.py` con la clase abstracta
  `VideoSourcePort` (`start()`, `stop()`, `on_frame(callback)`), idempotente
  en `stop()`. *(RF-4)*
  **Hecho cuando:** el módulo importa sin errores y una subclase mínima de
  prueba (sin lógica real) implementa los tres métodos sin excepciones.

- [x] **T-02 · Tabla `video_sessions`** — Extender `backend/db.py`:
  `CREATE TABLE IF NOT EXISTS video_sessions` con columnas `id`,
  `source_type` (`upload`|`live`), `source_ref`, `started_at`, `ended_at`,
  `status` (`active`|`finished`|`error`), `error_message`; agregar
  `backend/streaming/session_repository.py` con `create_session`,
  `update_session_status`, `close_session`. *(RF-7, RF-8)*
  **Hecho cuando:** al arrancar la app, `video_sessions` existe con esas
  columnas; insertar y actualizar una fila de prueba con el repositorio
  funciona sin error.

## Fase 1 — Fuente archivo (.mp4)

- [x] **T-03 · Adaptador `FileVideoSource`** — Crear
  `backend/streaming/sources/file_source.py`: implementa `VideoSourcePort`
  leyendo con `cv2.VideoCapture` desde un archivo temporal en un hilo
  propio, invoca `callback(frame)` por cada frame y libera el recurso en
  `stop()`. *(RF-2.1, RF-2.4)*
  **Hecho cuando:** con un `.mp4` de prueba en disco, `start()` +
  `on_frame()` entregan frames por el callback hasta terminar el video, y
  `stop()` cierra el `VideoCapture` sin dejar el archivo bloqueado.

- [x] **T-04 · Validación y subida del archivo** — En
  `backend/streaming/routes.py`, `POST /api/streaming/source` (multipart):
  valida extensión `.mp4` y tamaño ≤ 256 MB antes de guardar el archivo
  temporal; rechaza con `400` y mensaje en español si falla alguna
  validación; crea la sesión (`source_type = upload`) vía T-02.
  *(RF-1, RF-2.1, RF-2.2, RF-6)*
  **Hecho cuando:** con curl, un `.mp4` válido responde `202` con
  `session_id`; un archivo > 256 MB o con otra extensión responde `400` sin
  llegar a guardarse en disco.

- [x] **T-05 · Descarte del archivo al finalizar** — Al terminar el video
  (fin natural, `DELETE /api/streaming/source`, o cambio de fuente), borrar
  el archivo temporal y cerrar la sesión (`ended_at`, `status = finished`),
  conservando solo el nombre original en `source_ref`. *(RF-2.5, RF-5)*
  **Hecho cuando:** tras finalizar un análisis de archivo, el archivo
  temporal ya no existe en disco y la fila de `video_sessions` queda
  `finished` con `source_type = upload`.

- [x] **T-06 · Subida con progreso e indicador de subida (frontend)** — En
  `frontend/src/services/api.js`, función de subida vía `XMLHttpRequest`
  con evento `progress`; en `StreamView.vue`, selector de fuente
  archivo/cámara, input de archivo y barra de progreso. *(RF-1, RF-2.3)*
  **Hecho cuando:** al subir un `.mp4` desde el navegador se ve una barra de
  progreso que avanza hasta el 100 % antes de iniciar el análisis.

- [x] **T-07 · Reproductor con controles (frontend)** — En
  `StreamView.vue`, reproducir el archivo cargado con controles básicos
  (play/pause/seek) mientras el análisis corre en paralelo sobre
  `/api/stream`. *(RF-2.4)*
  **Hecho cuando:** con un archivo en análisis, el usuario puede pausar,
  reanudar y saltar en el reproductor sin que el backend deje de procesar
  frames.

## Fase 2 — Fuente cámara

- [x] **T-08 · Adaptador `CameraVideoSource`** — Crear
  `backend/streaming/sources/camera_source.py`: implementa
  `VideoSourcePort` sin abrir ningún recurso propio; `on_frame` solo
  registra el callback que invocará el endpoint de frames. *(RF-4)*
  **Hecho cuando:** `start()`/`stop()` no lanzan excepción sin cámara física
  conectada al servidor, y `on_frame()` guarda el callback correctamente
  (verificable con una llamada directa de prueba).

- [x] **T-09 · Endpoint de frames de cámara** — En
  `backend/streaming/routes.py`, `POST /api/streaming/camera-frame`:
  decodifica el JPEG del cuerpo e invoca el callback registrado; `409` si
  no hay sesión `live` activa; `POST /api/streaming/source` con
  `{"type": "live"}` crea la sesión (`source_type = live`) y activa
  `CameraVideoSource`. *(RF-1, RF-3.1, RF-3.3)*
  **Hecho cuando:** con curl, enviar un JPEG sin sesión `live` responde
  `409`; tras crear la sesión `live`, el mismo POST responde `204` y el
  frame llega al pipeline.

- [x] **T-10 · Selector de cámaras (frontend)** — Crear
  `frontend/src/services/videoCapture.js`: `enumerateDevices` para listar
  cámaras, `getUserMedia` con el `deviceId` elegido (o por defecto si no se
  selecciona ninguna); en `StreamView.vue`, selector de cámara visible solo
  para la fuente "cámara". *(RF-3.1, RF-3.2)*
  **Hecho cuando:** con ≥ 2 cámaras conectadas, el selector las lista todas
  y permite elegir una distinta a la por defecto antes de iniciar el
  análisis; con 0 cámaras, el selector muestra la lista vacía sin romper la
  UI.

- [x] **T-11 · Captura y envío periódico de frames (frontend)** —
  En `videoCapture.js`, capturar frames de la cámara seleccionada por
  `canvas` a 2–4 fps y enviarlos por `POST /api/streaming/camera-frame`
  mientras la sesión `live` esté activa; detener el envío en `stop()`.
  *(RF-3.1, RF-3.3)*
  **Hecho cuando:** al iniciar la fuente cámara, `/api/stream` muestra video
  en vivo con detecciones corriendo, sin pausa disponible en la UI para esta
  fuente.

## Fase 3 — Selección, cambio de fuente y errores

- [x] **T-12 · Factory de fuentes** — Crear
  `backend/streaming/sources/factory.py`: `create_video_source(type,
  **params)` devuelve `FileVideoSource` o `CameraVideoSource` según `type`;
  usado por `POST /api/streaming/source` en vez de un `if/elif` disperso.
  *(RF-1, RF-5)*
  **Hecho cuando:** llamar a la factory con `"upload"` o `"live"` devuelve
  la instancia correcta; con un tipo desconocido lanza un error claro.

- [x] **T-13 · Cambio de fuente y liberación de recursos** — En
  `backend/detection/pipeline.py` y `routes.py`: al recibir una nueva
  fuente o `DELETE /api/streaming/source`, llamar `stop()` sobre la fuente
  activa (libera `VideoCapture`, borra archivo temporal o descarta
  callback de cámara) antes de `start()` sobre la nueva; solo una fuente
  activa a la vez. *(RF-5)*
  **Hecho cuando:** cambiar de archivo a cámara (y viceversa) con un
  análisis en curso no deja procesos, hilos ni archivos temporales
  colgados, verificable revisando el sistema de archivos y los hilos
  activos tras el cambio.

- [x] **T-14 · Estado y errores claros** — `GET
  /api/streaming/source/status` devuelve `status` (`connecting`|
  `connected`|`error`) y `error_message`; ambos adaptadores marcan la
  sesión como `error` (permiso de cámara denegado, cámara desconectada,
  archivo corrupto o mayor a 256 MB) sin reintento automático.
  *(RF-3.4, RF-6)*
  **Hecho cuando:** denegar el permiso de cámara o desconectar la cámara en
  uso deja la sesión en `error` con un mensaje específico, visible una sola
  vez sin reintentos automáticos del backend.

- [x] **T-15 · Logging de sesiones** — Agregar logs (mismo patrón que
  `detection/pipeline.py`) de inicio/fin/error en `routes.py` y en cada
  adaptador. *(RF-7)*
  **Hecho cuando:** los logs del backend muestran una entrada de inicio y
  una de fin o error por cada sesión de video creada durante una prueba
  manual.

## Fase 4 — Verificación manual final

- [ ] **T-16 · Recorrido completo de verificación manual** — Ejecutar todos
  los casos de la sección 7 del plan (subida válida/ inválida, descarte de
  archivo, selección de cámara, denegación de permiso, desconexión de
  cámara, cambio de fuente, logs y `video_sessions`) y dejar constancia en
  el mensaje de commit de los criterios validados. *(RF-1–RF-8)*
  **Hecho cuando:** cada fila de la tabla de la sección 7 del plan se probó
  a mano con el resultado esperado, y el commit menciona explícitamente los
  RF verificados.
