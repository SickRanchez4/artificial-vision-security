# Plan técnico — Spec 001: MVP Monitoreo, reportes y chatbot

Plan de implementación de `_sdd/specs/spec-001-app-mvp/spec.md`. Respeta la
constitución: stack fijo (Flask, Vue, YOLO, OpenAI vía n8n, SQLite),
lógica solo en backend, sin tests automatizados (verificación manual),
identificadores en inglés y textos en español.

---

## 1. Estructura de módulos

```
backend/
  app.py                  # Fábrica de la app Flask y registro de blueprints
  config.py               # Configuración vía variables de entorno
  db.py                   # Conexión a SQLite y creación de tablas
  auth/
    routes.py             # Login/logout y protección de sesión        → RF-1
  streaming/
    routes.py             # Endpoint de transmisión MJPEG              → RF-2
    video_source.py       # Lectura del video en bucle + "sin señal"   → RF-2.1, RF-2.2
  detection/
    detector.py           # Inferencia YOLO por frame (umbral 25 %)    → RF-3.1
    pipeline.py           # Bucle de detección, captura y creación
                          #   de eventos                                → RF-3.2
    overlay.py            # Dibujo de recuadros sobre el frame         → RF-2.3
  events/
    repository.py         # CRUD de eventos en SQLite                  → RF-3.2, RF-5
    routes.py             # API de listado/detalle/imagen              → RF-5
  integrations/
    n8n_client.py         # Envío de eventos y preguntas a n8n         → RF-4.1, RF-6.1
    routes.py             # Webhook de retorno del análisis            → RF-4.2, RF-4.3
  chat/
    routes.py             # Proxy de preguntas del chatbot a n8n       → RF-6

frontend/
  src/
    router/index.js       # Rutas + guardia de autenticación           → RF-1.1
    stores/session.js     # Estado de sesión (Pinia no: composable propio,
                          #   sin dependencias extra)                  → RF-1
    views/
      LoginView.vue       # Inicio de sesión                           → RF-1
      StreamView.vue      # Transmisión en vivo / "cámara sin señal"   → RF-2
      ReportsView.vue     # Panel de reportes (lista + detalle)        → RF-5
      ChatView.vue        # Chatbot sobre reportes                     → RF-6
    services/api.js       # Único punto de acceso a la API REST Flask
```

- El frontend **solo** consume la API REST de Flask (constitución, principio 3):
  ni YOLO, ni OpenAI, ni URLs de n8n aparecen en `frontend/`.
- El bucle de detección corre en el servidor como hilo del backend, independiente
  de que haya navegadores conectados (caso límite "sesión expirada").

## 2. Modelo de datos (SQLite)

Dos tablas: `users` y `detection_events`. Los mensajes del chatbot no se
persisten (RF-6.4).

### Tabla `users` → RF-1

| Columna         | Tipo          | Notas                     |
|-----------------|---------------|---------------------------|
| `id`            | integer PK autoincrement |               |
| `username`      | text unique   |                           |
| `password_hash` | text          | Hash (werkzeug, ya incluido en Flask) |

### Tabla `detection_events` → RF-3.2, RF-4, RF-5, sección "Datos persistidos"

| Columna           | Tipo                     | Notas                                        |
|-------------------|--------------------------|----------------------------------------------|
| `id`              | text PK (UUID)           | Identificador del evento (contrato con n8n)  |
| `detected_at`     | text (ISO 8601 UTC)      | Fecha y hora de la detección                 |
| `weapon_class`    | text                     | `weapon`                                     |
| `confidence`      | real                     | 0.25 – 1.00                                  |
| `image`           | blob                     | Captura íntegra, sin difuminado (RNF-2)      |
| `analysis_status` | text                     | `pending` \| `done` \| `failed`              |
| `report_text`     | text nullable            | Texto del reporte del LLM (solo si `done`)   |

### Ejemplo de evento serializado en JSON (respuesta de la API)

```json
{
  "id": "9f1b2c3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d",
  "detected_at": "2026-08-31T14:22:05-04:00",
  "weapon_class": "firearm",
  "weapon_class_label": "Arma de fuego",
  "confidence": 0.87,
  "analysis_status": "done",
  "analysis_status_label": "Análisis: realizado",
  "report_text": "Se observa a una persona portando un arma de fuego corta cerca del acceso principal...",
  "image_url": "/api/events/9f1b2c3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d/image"
}
```

Las etiquetas (`*_label`) las genera el backend en español (constitución,
principio 6); el frontend solo las muestra.

## 3. Contratos de la app

### 3.1 API REST interna (frontend ↔ Flask)

| Método/Ruta | Entrada | Salida | RF |
|---|---|---|---|
| `POST /api/login` | `{ "username", "password" }` | `200 {"ok": true}` con cookie de sesión · `401 {"error": "Credenciales inválidas."}` (mensaje único, sin revelar el campo) | RF-1.2, RF-1.3 |
| `POST /api/logout` | — | `200` | RF-1 |
| `GET /api/stream` | — (sesión requerida) | `multipart/x-mixed-replace` (MJPEG) con los recuadros ya dibujados por el backend; si no hay fuente, frames con estado y cabecera `X-Camera-Status: offline` | RF-2.1, RF-2.2, RF-2.3 |
| `GET /api/events` | — (sesión requerida) | `200 [evento, ...]` orden descendente por `detected_at`; `[]` si no hay | RF-5.1, RF-5.3 |
| `GET /api/events/<id>` | — | `200 evento` (JSON del ejemplo) · `404` | RF-5.2 |
| `GET /api/events/<id>/image` | — (sesión requerida) | `200 image/jpeg` · `404` | RF-5.1, RNF-2 |
| `POST /api/chat` | `{ "question": "...", "conversation_id": "uuid" }` | `200 { "answer": "..." }` · `502 {"error": "El asistente no está disponible. Intenta de nuevo."}` | RF-6.1, RF-6.3 |

Toda ruta salvo `/api/login` responde `401` sin sesión → el frontend redirige
al login (RF-1.1).

### 3.2 Contrato de salida hacia n8n — análisis de evento → RF-4.1

`POST {N8N_ANALYSIS_WEBHOOK_URL}` (variable de entorno del backend), JSON:

```json
{
  "event_id": "9f1b2c3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d",
  "detected_at": "2026-08-31T14:22:05-04:00",
  "weapon_class": "firearm",
  "confidence": 0.87,
  "image_base64": "<JPEG en base64>",
  "callback_url": "{APP_BASE_URL}/api/n8n/analysis-result"
}
```

n8n analiza con el LLM, notifica por Telegram (flujo existente, fuera de
alcance) y responde por el callback.

### 3.3 Contrato de entrada desde n8n — resultado del análisis → RF-4.2, RF-4.3

`POST /api/n8n/analysis-result`, autenticado con token compartido en cabecera
`X-Webhook-Token` (variable de entorno en ambos lados), JSON:

```json
{
  "event_id": "9f1b2c3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d",
  "status": "success",
  "report_text": "Se observa a una persona portando un arma de fuego corta..."
}
```

Reglas:
- `status = "success"` → guardar `report_text`, `analysis_status = done` (RF-4.2).
- `status = "error"` o `event_id` desconocido → `analysis_status = failed` /
  descartar respuesta sin alterar eventos (RF-4.3, caso límite).
- Timeout del envío inicial (sin respuesta de n8n en `N8N_TIMEOUT_SECONDS`) →
  `analysis_status = failed`, sin reintento (RF-4.3).
- Respuesta tardía válida → se asocia por `event_id` aunque el evento ya esté
  `failed` (caso límite "n8n responde tarde").

### 3.4 Contrato del chatbot (Flask ↔ n8n) → RF-6.1

Síncrono, sin persistencia (RF-6.4): `POST {N8N_CHAT_WEBHOOK_URL}`:

```json
{ "conversation_id": "uuid", "question": "¿Cuántas detecciones hubo hoy?" }
```

Respuesta esperada de n8n (que consulta la BD de reportes directamente):

```json
{ "answer": "Hoy se registraron 3 detecciones: 2 armas de fuego y 1 arma blanca." }
```

Sin respuesta o error → Flask devuelve `502` al frontend con mensaje en
español y el usuario puede reintentar (RF-6.3). El acotamiento temático
(RF-6.2) es responsabilidad del prompt del flujo n8n, fuera de alcance.

## 4. Decisiones técnicas justificadas

1. **MJPEG (`multipart/x-mixed-replace`) para la transmisión** — es HTTP puro
   servido por Flask, sin WebSockets ni servidores de streaming adicionales
   (principio 1: simplicidad). Latencia y calidad suficientes para un demo
   (RNF-3). El backend dibuja los recuadros antes de emitir el frame, así el
   frontend no conoce nada de YOLO (principio 3).
2. **Bucle de detección como hilo del backend** — la detección no depende del
   navegador; se muestrea ~2-4 frames/s para inferencia (suficiente para el
   demo y muy por debajo de los 5 s de RNF-3), aunque el stream se emita a más
   FPS.
3. **Sin enfriamiento (cooldown): cada frame analizado genera un evento por
   detección de arma** — simplifica el pipeline; si el volumen de eventos
   resulta excesivo en un uso real, se reevaluará en una spec posterior.
4. **Imágenes en `blob` dentro de SQLite** — evita gestionar un
   directorio de archivos con permisos propios; todo dato sensible queda en un
   único lugar con acceso por sesión (RNF-2, principio 5). Volumen del MVP
   (1 cámara, enfriamiento 20 s) lo hace viable. SQLite es un único archivo
   local, suficiente para el volumen y el despliegue de 1 solo desarrollador
   del MVP; se reevaluará si el proyecto crece a múltiples instancias.
5. **Callback asíncrono para el análisis, síncrono para el chat** — el
   análisis puede tardar (LLM + Telegram), por eso n8n responde por webhook con
   token compartido; el chat es interactivo y una respuesta síncrona simplifica
   el flujo y cumple RF-6 sin estado adicional. Configuración de n8n solo por
   variables de entorno (`N8N_ANALYSIS_WEBHOOK_URL`, `N8N_CHAT_WEBHOOK_URL`,
   `N8N_WEBHOOK_TOKEN`, `N8N_TIMEOUT_SECONDS`), sin endpoints de configuración.
6. **Sesión de Flask con cookie (login simple)** — un solo rol (spec), sin JWT
   ni librerías extra: `session` de Flask + hash de contraseña de werkzeug
   (incluido en Flask). Cumple RF-1 sin ampliar el stack.
7. **Sin ORM: SQL directo con `sqlite3` (librería estándar)** — dos tablas y
   consultas triviales; un ORM añadiría dependencia y complejidad sin
   beneficio (principio 1).
8. **Etiquetas en español generadas por el backend** — centraliza el idioma de
   los mensajes (principio 6) y mantiene el frontend como capa de presentación
   pura (principio 3).

## 5. Dependencias previstas (trazadas a la spec)

| Dependencia | Justificación |
|---|---|
| `flask` | Backend y API REST (constitución, stack) |
| `ultralytics` (YOLO) + `opencv-python` | RF-2, RF-3: detección y lectura del video en bucle |
| `ultralytics/CLIP` | RF-3.1: vocabulario abierto `gun`/`knife` de YOLO-World |
| `sqlite3` (librería estándar de Python) | Principio 5: persistencia local en un único archivo, sin servicio externo |
| `requests` | RF-4.1, RF-6.1: llamadas HTTP a n8n |
| `vue` + `vue-router` | Frontend SPA con pestañas (RF-1.2) |
| `vite` + `@vitejs/plugin-vue` | T-03: servidor y compilación de componentes Vue del frontend |

Cualquier dependencia fuera de esta tabla exige actualizar primero la spec
(principio 1).

## 6. Cobertura de requisitos

| RF | Cubierto por |
|---|---|
| RF-1.1–1.3 | `auth/routes.py`, guardia en `router/index.js`, contrato `/api/login` |
| RF-2.1–2.3 | `streaming/`, `detection/overlay.py`, contrato `/api/stream` |
| RF-3.1–3.2 | `detection/detector.py` (umbral 25 % inclusivo), `detection/pipeline.py`, tabla `detection_events` |
| RF-4.1–4.3 | `integrations/n8n_client.py`, `integrations/routes.py`, contratos 3.2 y 3.3 |
| RF-5.1–5.3 | `events/routes.py`, `ReportsView.vue`, contratos `/api/events*` |
| RF-6.1–6.4 | `chat/routes.py`, `ChatView.vue`, contrato 3.4, sin persistencia de chat |
| RNF-1 | Etiquetas y errores generados en español por el backend |
| RNF-2 | Imágenes en BD, acceso solo con sesión |
| RNF-3 | Muestreo 2-4 fps + inserción inmediata del evento |
| RNF-4 | `video_source.py` (sin señal) y manejo de timeout de n8n |
