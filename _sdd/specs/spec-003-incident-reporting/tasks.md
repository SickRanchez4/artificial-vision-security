# Tareas — Spec 003: incident reporting

Derivadas de `spec.md` y `plan.md`. Orden de dependencia: cada tarea asume
completadas las anteriores. Sin tests automatizados: verificación manual a
cargo del desarrollador (constitución, principio 4; plan, sección 7).

## Fase 0 — Modelo de datos y configuración

- [x] **T-01 · Columnas nuevas en `detection_events`** — En `backend/db.py`,
  agregar `suspects_number` (INTEGER, nullable) y `suspects_description`
  (TEXT, nullable) a `detection_events` mediante `ALTER TABLE` idempotente
  (envuelto en `try/except sqlite3.OperationalError`) dentro de
  `init_database()`. *(Datos persistidos)*
  **Hecho cuando:** al arrancar la app sobre una base de datos ya existente
  y también sobre una nueva, `detection_events` queda con ambas columnas
  sin lanzar error.

- [x] **T-02 · Configuración de confirmación y enfriamiento** — En
  `backend/config.py`, agregar `CONFIRMATION_FRAMES = 3` y
  `INCIDENT_COOLDOWN_SECONDS = 15`; subir el valor por defecto de
  `N8N_TIMEOUT_SECONDS` de `10` a `30`. *(RF-1, RF-3, duda abierta del plan)*
  **Hecho cuando:** `current_app.config["CONFIRMATION_FRAMES"] == 3`,
  `current_app.config["INCIDENT_COOLDOWN_SECONDS"] == 15` y
  `N8N_TIMEOUT_SECONDS` es `30` sin variable de entorno definida.

## Fase 1 — Confirmación por frames consecutivos

- [x] **T-03 · `IncidentConfirmationTracker`** — Crear
  `backend/detection/incident_tracker.py` con la clase
  `IncidentConfirmationTracker`: `observe(frame, detections)` devuelve un
  `ConfirmedIncident` (frame + detección) solo al completar
  `CONFIRMATION_FRAMES` detecciones de `weapon` estrictamente consecutivas,
  y `None` en cualquier otro caso; `reset()` descarta el seguimiento en
  curso sin registrar nada. *(RF-1.1, RF-1.2, RF-1.4)*
  **Hecho cuando:** con una prueba manual invocando `observe()` con listas
  de detecciones simuladas (3 seguidas → devuelve `ConfirmedIncident` en la
  tercera llamada; menos de 3 → devuelve `None` en todas).

- [x] **T-04 · Reseteo por frame sin detección** — En
  `IncidentConfirmationTracker.observe()`, si el frame no trae detección de
  `weapon`, reiniciar `consecutive_count` a 0 sin generar
  `ConfirmedIncident`. *(RF-1.3)*
  **Hecho cuando:** una secuencia detección→sin detección→detección→detección
  no confirma en la 3.ª llamada (porque el conteo se reinició), solo tras 3
  detecciones consecutivas nuevas.

- [x] **T-05 · Enfriamiento tras confirmación** — En
  `IncidentConfirmationTracker`, al confirmar (T-03) fijar
  `cooldown_until = now + INCIDENT_COOLDOWN_SECONDS`; mientras
  `now < cooldown_until`, `observe()` devuelve `None` de inmediato sin
  avanzar ningún conteo. *(RF-3.1, RF-3.2)*
  **Hecho cuando:** tras una confirmación, llamadas a `observe()` con
  detecciones válidas dentro de los 15 s siguientes devuelven `None`; pasado
  ese tiempo, una nueva secuencia de 3 detecciones vuelve a confirmar.

- [x] **T-06 · Reseteo por interrupción de fuente** — Exponer
  `IncidentConfirmationTracker.reset()` y llamarlo desde
  `backend/detection/pipeline.py` en `stop_active_source()` y al inicio de
  `set_active_source()` (antes de activar la nueva fuente). *(RF-1.5)*
  **Hecho cuando:** con un seguimiento a mitad de confirmar (1 o 2 frames),
  cambiar o detener la fuente activa hace que la siguiente detección en la
  nueva fuente empiece el conteo desde cero, sin arrastrar el estado
  anterior.

## Fase 2 — Verificación del incidente vía n8n

- [x] **T-07 · Llamada síncrona a n8n** — En
  `backend/integrations/n8n_client.py`, modificar `send_event_for_analysis`
  (o crear una función nueva) para hacer `requests.post(...)` de forma
  **síncrona**, sin `callback_url`, y parsear el JSON de respuesta
  (`is_real_incident`, `report_text`, `suspects_number`,
  `suspects_description`). *(RF-2.1, RF-2.2)*
  **Hecho cuando:** contra un stub HTTP local que responde el JSON de
  ejemplo, la función retorna esos cuatro campos ya parseados en un dict o
  estructura equivalente.

- [x] **T-08 · Registrar incidencia real** — Cuando la respuesta traiga
  `is_real_incident: true`, llamar a `events.repository.create_event` con
  estado `done` y los campos `report_text`, `suspects_number`,
  `suspects_description` ya poblados. *(RF-2.3)*
  **Hecho cuando:** con el stub respondiendo `is_real_incident: true`,
  `GET /api/events` muestra el nuevo evento con `analysis_status = done` y
  los tres campos del análisis con los valores del stub.

- [x] **T-09 · Descartar incidencia no real** — Cuando la respuesta traiga
  `is_real_incident: false`, no llamar a `create_event` ni guardar ninguna
  imagen. *(RF-2.4)*
  **Hecho cuando:** con el stub respondiendo `is_real_incident: false`, el
  conteo de filas en `detection_events` no cambia tras la llamada.

- [x] **T-10 · Registrar fallo (sin respuesta válida)** — Ante timeout,
  error HTTP, excepción de red, o `is_real_incident` ausente/no booleano,
  llamar a `create_event` con estado `failed`, sin `report_text` ni
  `suspects_*` (quedan en `NULL`). *(RF-2.5)*
  **Hecho cuando:** simulando cada caso (stub caído, stub con timeout, stub
  respondiendo `is_real_incident: "si"`), en los tres se crea un evento con
  `analysis_status = failed` y los tres campos de análisis en `null`.

- [x] **T-11 · Actualizar `events/repository.py`** — Extender
  `create_event` para aceptar `analysis_status` inicial (`done`|`failed`,
  ya no solo `pending`), `report_text`, `suspects_number` y
  `suspects_description` como parámetros opcionales en la creación.
  *(RF-2.3, RF-2.5, Datos persistidos)*
  **Hecho cuando:** llamar a `create_event` con estado `done` y los tres
  campos de análisis los persiste correctamente en una sola inserción,
  verificable leyendo la fila con `get_event`.

## Fase 3 — Integración en el pipeline y limpieza

- [x] **T-12 · Reemplazar `_create_events` por el tracker** — En
  `backend/detection/pipeline.py`, sustituir la creación de un evento por
  cada frame detectado (`_create_events`) por: en cada frame, ejecutar
  detección → pasar `(frame, detections)` a
  `IncidentConfirmationTracker.observe()` → si devuelve
  `ConfirmedIncident`, lanzar en un hilo la llamada síncrona a n8n (T-07) y
  el registro correspondiente (T-08/T-09/T-10). *(RF-1.1–RF-1.4, RF-2.1)*
  **Hecho cuando:** con `DEBUG_DISABLE_EVENTS = False` y un video de prueba
  donde un arma aparece en ≥ 3 frames consecutivos, se genera como máximo un
  evento por esa secuencia (no uno por frame).

- [x] **T-13 · Retirar el callback asíncrono de n8n** — Eliminar el
  endpoint `POST /api/n8n/analysis-result` de
  `backend/integrations/routes.py` y el uso de `N8N_WEBHOOK_TOKEN` que ya
  no aplica a esta spec. *(Decisión 3 del plan)*
  **Hecho cuando:** el endpoint ya no existe (una petición a esa ruta
  responde `404`) y la app arranca sin errores sin referencias rotas a
  `update_analysis` desde ese blueprint.

## Fase 4 — Verificación manual final

- [ ] **T-14 · Recorrido completo de verificación manual** — Ejecutar todos
  los casos de la sección 7 del plan (confirmación en 3 frames, reseteo por
  frame perdido, incidente real, incidente descartado, fallo/timeout de
  n8n, interrupción de fuente durante confirmación, enfriamiento de 15 s) y
  dejar constancia en el mensaje de commit de los criterios validados.
  *(RF-1–RF-3, Datos persistidos)*
  **Hecho cuando:** cada fila de la tabla de la sección 7 del plan se probó
  a mano con el resultado esperado, y el commit menciona explícitamente los
  RF verificados.

