# Plan técnico — Spec 003: incident reporting

Plan de implementación de `_sdd/specs/spec-003-incident-reporting/spec.md`.
Respeta la constitución: stack fijo (Flask, YOLO y n8n ya usados), lógica de
confirmación y verificación **solo en el backend**, sin nuevas dependencias,
**sin tests automatizados** (principio 4: verificación manual, sección 7),
identificadores en inglés y comentarios/mensajes en español.

---

## 1. Estructura de módulos

```
backend/
  detection/
    incident_tracker.py   # NUEVO — máquina de estados de confirmación (3
                           #   frames consecutivos) + enfriamiento de 15 s.
                           #   Sin hilos propios: la invoca pipeline.py en
                           #   cada frame procesado.                          → RF-1, RF-3
    pipeline.py            # MODIFICADO — _create_events() se reemplaza por
                           #   una llamada al tracker; ya no crea un evento
                           #   por frame, solo cuando el tracker confirma.     → RF-1.1–1.5
  integrations/
    n8n_client.py          # MODIFICADO — send_event_for_analysis() pasa de
                           #   "disparar y olvidar" (hilo + callback) a una
                           #   llamada POST síncrona que devuelve
                           #   is_real_incident/report_text/suspects_*.       → RF-2.1–2.5
    routes.py               # MODIFICADO — se retira el endpoint
                           #   POST /api/n8n/analysis-result: ya no hay
                           #   callback asíncrono que atender.                → RF-2.2
  events/
    repository.py          # MODIFICADO — create_event() recibe también
                           #   suspects_number/suspects_description y el
                           #   estado final (done/failed) desde el inicio;
                           #   ya no existe el estado intermedio "pending"
                           #   para incidencias de esta spec.                 → RF-2.3, RF-2.5
  db.py                    # MODIFICADO — columnas nuevas en detection_events
                           #   (suspects_number, suspects_description).       → "Datos persistidos"
  config.py                # MODIFICADO — CONFIRMATION_FRAMES=3,
                           #   INCIDENT_COOLDOWN_SECONDS=15, y se sube el
                           #   valor por defecto de N8N_TIMEOUT_SECONDS.      → RF-1, RF-3, duda abierta
```

- `detection/detector.py`, `detection/overlay.py` y el resto del pipeline de
  inferencia YOLO **no se tocan** (fuera de alcance de la spec).
- No hay cambios en `frontend/`: esta spec es puramente de backend
  (constitución, principio 3); el panel de reportes ya muestra
  `report_text` y solo necesita los dos campos nuevos, que llegan por la
  misma ruta `GET /api/events` existente.

## 2. Modelo de datos (SQLite)

`detection_events` (ya existente desde spec-001) gana dos columnas nuevas;
no se crea ninguna tabla nueva.

### Cambios en `detection_events` → RF-2.3, RF-2.5, "Datos persistidos"

| Columna                 | Tipo | Notas |
|--------------------------|------|-------|
| `suspects_number`        | INTEGER, nullable | Cantidad de sospechosos reportada por n8n; `NULL` si el análisis fue fallido |
| `suspects_description`   | TEXT, nullable | Descripción textual (español) de los sospechosos; `NULL` si el análisis fue fallido |

- Se agregan con `ALTER TABLE detection_events ADD COLUMN ...` dentro de
  `init_database()`, envuelto en `try/except sqlite3.OperationalError` para
  que sea idempotente (mismo patrón `CREATE TABLE IF NOT EXISTS` ya usado;
  no se introduce un framework de migraciones para dos columnas).
- `analysis_status` conserva su `CHECK IN ('pending', 'done', 'failed')`
  para no romper el esquema existente, aunque esta spec ya no usa
  `'pending'`: el evento se crea **directamente** en `done` o `failed`,
  nunca antes de tener la respuesta de n8n (RF-2.2).
- `report_text`, `suspects_number` y `suspects_description` quedan en
  `NULL` cuando `analysis_status = 'failed'` (RF-2.5).
- No se persiste ninguna fila para: seguimientos no confirmados (RF-1.3),
  interrumpidos por cambio de fuente (RF-1.5), o con
  `is_real_incident: false` (RF-2.4) — coherente con "Datos persistidos".

## 3. Contratos de la app

No se añade ni modifica ningún endpoint público de la API REST: esta spec
es un cambio de comportamiento interno del pipeline y del cliente de n8n.
`GET /api/events` y `GET /api/events/<id>` (spec-001) exponen los campos
nuevos automáticamente al serializar la fila.

### 3.1 Contrato interno `IncidentConfirmationTracker` → RF-1, RF-3

```python
class IncidentConfirmationTracker:
    def observe(self, frame, detections: list[dict]) -> ConfirmedIncident | None:
        """Se llama una vez por frame procesado. Devuelve un
        ConfirmedIncident (frame + detection) solo en el frame donde se
        completan las 3 detecciones consecutivas; en cualquier otro caso
        devuelve None (incluye: sin detección, en enfriamiento, o
        seguimiento aún incompleto)."""

    def reset(self) -> None:
        """Descarta cualquier seguimiento en curso, sin registrar nada.
        La llama pipeline.py cuando la fuente activa se detiene/cambia
        (RF-1.5)."""
```

- Estado interno mínimo: `consecutive_count`, `last_detection` (frame +
  metadata del último frame visto) y `cooldown_until` (timestamp).
- `observe()` decide en este orden: si `now < cooldown_until` → ignora
  (RF-3.2); si no hay detección de `weapon` → resetea `consecutive_count` a
  0 (RF-1.3); si hay detección → incrementa `consecutive_count` y guarda el
  frame/confianza actuales como candidatos; al llegar a 3 → arma
  `cooldown_until = now + 15s` (RF-3.1), resetea `consecutive_count` y
  devuelve el `ConfirmedIncident` con los datos del frame recién procesado
  (el tercero, RF-1.4).
- Un único tracker por proceso, igual que un único `_active_source` activo
  a la vez en `pipeline.py` (no se contempla más de un seguimiento
  concurrente, ver "Fuera de alcance").

### 3.2 Contrato HTTP con n8n → RF-2.1–2.5

**Petición** (`POST` a `N8N_ANALYSIS_WEBHOOK_URL`, `multipart/form-data`:
la imagen viaja como archivo binario real, no como texto base64, para que
el nodo Webhook de n8n la reciba automáticamente en formato binario;
se retira `callback_url` porque ya no hay callback):

- Campos de formulario: `event_id`, `detected_at` (ISO 8601), `weapon_class`,
  `confidence`.
- Archivo: `image` — JPEG del último frame confirmado (`image/jpeg`).

**Respuesta esperada** (síncrona, del nodo "Respond to Webhook"):

```json
{
  "is_real_incident": true,
  "report_text": "texto en español",
  "suspects_number": 1,
  "suspects_description": "texto en español"
}
```

- `is_real_incident` ausente, no booleano, o cualquier excepción de red /
  HTTP / timeout / JSON inválido → se trata como fallo (RF-2.5); el resto
  de campos se ignoran en ese caso.
- El timeout de la llamada sigue siendo `N8N_TIMEOUT_SECONDS` (ver decisión
  6 más abajo).

## 4. Decisiones técnicas justificadas

1. **Confirmación como máquina de estados en memoria (`incident_tracker.py`),
   no en base de datos** — el seguimiento de 3 frames es efímero y de
   altísima frecuencia (varios por segundo); persistirlo agregaría E/S
   innecesaria para un estado que, según la spec, se puede perder sin
   problema si el backend reinicia (caso límite ya aceptado).
2. **Llamada a n8n síncrona (bloqueante) en el hilo de envío, ya no en
   "disparar y olvidar"** — la spec exige esperar la respuesta del nodo
   "Respond to Webhook" (RF-2.2) para decidir si se persiste el evento; se
   sigue lanzando en un hilo (`threading.Thread`, patrón ya usado en
   `pipeline.py`) para no bloquear el procesamiento de frames del video
   mientras se espera la respuesta de n8n.
3. **Se retira el endpoint `POST /api/n8n/analysis-result`** — con la
   respuesta síncrona, el callback asíncrono de spec-001 queda sin uso; no
   se conserva "por si acaso" (principio de no añadir complejidad no
   pedida). `N8N_WEBHOOK_TOKEN` deja de ser necesario y puede eliminarse de
   `config.py` en la implementación.
4. **El evento se crea una sola vez, ya con estado final (`done`/`failed`)**
   — a diferencia de spec-001 (crear en `pending` y actualizar después), ya
   no hace falta el estado intermedio porque la respuesta de n8n llega
   antes de escribir en la base de datos (RF-2.2 lo garantiza).
5. **Columnas nuevas con `ALTER TABLE` idempotente en vez de tabla
   separada** — `suspects_number`/`suspects_description` son atributos 1:1
   del evento, no una entidad propia; una tabla aparte obligaría a un JOIN
   sin necesidad real (simplicidad, principio 1).
6. **Subir el valor por defecto de `N8N_TIMEOUT_SECONDS` de 10 a 30
   segundos** — resuelve la duda abierta de la spec: al incluir ahora un
   análisis LLM completo (antes async, ahora bloqueante) 10 s es
   insuficiente en la mayoría de los casos; sigue siendo configurable por
   variable de entorno sin cambiar comportamiento funcional.
7. **Enfriamiento (`cooldown_until`) dentro del mismo tracker, no como un
   scheduler/job separado** — es un simple timestamp comparado en cada
   `observe()`; no se justifica un componente adicional (APScheduler, hilos
   de temporizador) para una espera fija de 15 s.

## 5. Dependencias previstas (trazadas a la spec)

Ninguna dependencia nueva. Se reutiliza `requests` (ya en
`requirements.txt`, usado por `integrations/n8n_client.py` desde spec-001)
para la llamada síncrona a n8n. Cualquier adición futura exige actualizar
primero la spec (principio 1).

## 6. Cobertura de requisitos

| RF | Cubierto por |
|---|---|
| RF-1.1–1.3 | `detection/incident_tracker.py` (`observe`, conteo consecutivo y reseteo) |
| RF-1.4 | `incident_tracker.py` devuelve el `ConfirmedIncident` con el frame/detección del tercer frame |
| RF-1.5 | `pipeline.py` llama a `tracker.reset()` en `stop_active_source()` / `set_active_source()` |
| RF-2.1 | `integrations/n8n_client.py` (payload de la petición) |
| RF-2.2 | `n8n_client.py` (llamada síncrona con `requests.post(...).json()`) |
| RF-2.3 | `events/repository.py` (`create_event` con estado `done` + `report_text`/`suspects_*`) |
| RF-2.4 | `n8n_client.py` descarta sin llamar a `create_event` cuando `is_real_incident is False` |
| RF-2.5 | `n8n_client.py` captura excepciones/timeout/JSON inválido → `create_event` con estado `failed` |
| RF-3.1–3.2 | `incident_tracker.py` (`cooldown_until`), consultado en cada `observe()` |
| "Datos persistidos" | `db.py` (columnas nuevas), `events/repository.py` |

## 7. Estrategia de verificación (manual, a cargo del desarrollador)

No se implementan pruebas automatizadas (constitución, principio 4): el
único desarrollador ejecuta esta verificación a mano antes de cada commit
que toque esta spec, y deja constancia en el mensaje de commit de qué
criterios se validaron. Para simular respuestas de n8n sin depender del
flujo real, se recomienda un stub local (servidor mínimo o mock de
`requests.post`) que permita forzar cada uno de los casos de la tabla.

| Caso | Resultado esperado | RF |
|---|---|---|
| Arma detectada en 3 frames consecutivos, n8n responde `is_real_incident: true` | Un solo evento en `GET /api/events` con `report_text`, `suspects_number`, `suspects_description`, `analysis_status = done` | RF-1.4, RF-2.1–2.3 |
| Arma detectada en el 1.er frame, ausente en el 2.º | No se envía nada a n8n, no aparece ningún evento nuevo | RF-1.3 |
| Arma detectada en 3 frames consecutivos, n8n responde `is_real_incident: false` | No se registra ningún evento nuevo | RF-2.4 |
| n8n no responde / responde con error HTTP / timeout | Se crea un evento con `analysis_status = failed`, sin `report_text` ni `suspects_*` | RF-2.5 |
| n8n responde `is_real_incident` ausente o no booleano | Igual al caso anterior (tratado como fallo) | RF-2.5 |
| Cambiar la fuente de video mientras se cuentan los 3 frames | El seguimiento se descarta; ningún evento se genera con esa captura | RF-1.5 |
| Tras un envío a n8n (cualquier resultado), nueva arma detectada antes de 15 s | Se ignora sin iniciar seguimiento | RF-3.1, RF-3.2 |
| Nueva arma detectada después de los 15 s de enfriamiento | Inicia un nuevo seguimiento normalmente | RF-3.1 |
| Revisar la base de datos tras cada caso anterior | Solo existen filas para los casos "incidente real" y "fallo"; ninguna para los descartados | "Datos persistidos" |

Casos ya cubiertos por spec-001/spec-002 (autenticación, ingestión de video,
panel de reportes) no se repiten aquí.

