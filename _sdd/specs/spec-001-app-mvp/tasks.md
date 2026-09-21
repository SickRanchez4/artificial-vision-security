# Tareas — Spec 001: MVP Monitoreo, reportes y chatbot

Derivadas de `spec.md` y `plan.md`. Orden de dependencia: cada tarea asume
completadas las anteriores. Verificación manual (constitución, principio 4).

## Fase 0 — Cimientos

- [x] **T-01 · Esqueleto del backend Flask** — Crear `backend/` con fábrica de
  app, `config.py` leyendo variables de entorno (`SQL_SERVER_CONNECTION_STRING`,
  `N8N_ANALYSIS_WEBHOOK_URL`, `N8N_CHAT_WEBHOOK_URL`, `N8N_WEBHOOK_TOKEN`,
  `N8N_TIMEOUT_SECONDS`, `APP_BASE_URL`, `VIDEO_SOURCE_PATH`) y registro de
  blueprints vacíos. *(base para todos los RF)*
  **Hecho cuando:** `flask --app backend/app run --debug` arranca sin errores.

- [x] **T-02 · Base de datos** — Crear `db.py` con conexión `pyodbc` y creación
  de tablas `users` y `detection_events` según el modelo del plan. *(RF-3.2, RF-1)*
  **Hecho cuando:** al arrancar la app, ambas tablas existen en SQL Server y
  una consulta a `INFORMATION_SCHEMA.TABLES` las muestra con las columnas del plan.

- [x] **T-03 · Esqueleto del frontend Vue** — Crear `frontend/` (Vue 3 +
  vue-router) con las 4 vistas vacías (login, transmisión, reportes, chatbot),
  navegación por pestañas y `services/api.js` como único acceso a la API. *(RF-1.2)*
  **Hecho cuando:** `npm run dev` sirve la SPA y se puede navegar entre las
  tres pestañas y el login.

## Fase 1 — Autenticación

- [x] **T-04 · Login en el backend** — `auth/routes.py`: `POST /api/login`
  (sesión por cookie, error único en español), `POST /api/logout`, y
  protección `401` en todas las rutas de API salvo login; usuario semilla con
  hash werkzeug. *(RF-1.1, RF-1.2, RF-1.3)*
  **Hecho cuando:** con curl, credenciales válidas devuelven `200` + cookie;
  inválidas `401` con "Credenciales inválidas."; cualquier otra ruta sin
  cookie devuelve `401`.

- [x] **T-05 · Login en el frontend** — `LoginView.vue` + guardia de rutas +
  composable de sesión; redirección al login ante `401`. *(RF-1.1, RF-1.2, RF-1.3)*
  **Hecho cuando:** sin sesión, cualquier URL redirige al login; con login
  correcto se accede a las tres pestañas; con credenciales malas se ve el
  mensaje de error en español.

## Fase 2 — Video y detección

- [x] **T-06 · Fuente de video en bucle** — `streaming/video_source.py`: lee
  `VIDEO_SOURCE_PATH` con OpenCV, reinicia al terminar (bucle) y expone estado
  "sin señal" si el archivo no está disponible. *(RF-2.1, RF-2.2)*
  **Hecho cuando:** con un video presente entrega frames en bucle; al quitar
  el archivo, reporta estado sin señal sin lanzar excepción.

- [x] **T-07 · Stream MJPEG** — `streaming/routes.py`: `GET /api/stream`
  (multipart/x-mixed-replace, sesión requerida); frames de "cámara sin señal"
  cuando no hay fuente. *(RF-2.1, RF-2.2)*
  **Hecho cuando:** el navegador autenticado muestra el video en bucle en
  `/api/stream`; sin el archivo de video se ve el aviso "cámara sin señal".

- [x] **T-08 · Detector YOLO** — `detection/detector.py`: inferencia sobre un
  frame, clases arma de fuego / arma blanca, umbral de confianza ≥ 25 %
  inclusivo (descarta el resto). *(RF-3.1)*
  **Hecho cuando:** con una imagen de prueba con arma devuelve clase y
  confianza; con confianza < 25 % no devuelve detección.

- [x] **T-09 · Recuadros sobre el stream** — `detection/overlay.py` + conexión
  al stream: dibujar recuadro y etiqueta en español sobre las detecciones
  antes de emitir el frame. *(RF-2.3)*
  **Hecho cuando:** al aparecer un arma en el video, el stream muestra el
  recuadro sobre el objeto; el frontend no contiene referencias a YOLO
  (`grep yolo frontend/` → 0).

- [x] **T-10 · Pipeline de eventos con enfriamiento** — `detection/pipeline.py`:
  hilo del backend que muestrea 2-4 fps, y al detectar crea el evento
  (uuid, timestamp, clase, confianza, JPEG íntegro en `varbinary(max)`,
  `analysis_status = pending`) respetando enfriamiento de 20 s por clase;
  dos clases simultáneas generan dos eventos. *(RF-3.1, RF-3.2, RF-3.3)*
  **Hecho cuando:** un arma visible 60 s seguidos genera como máximo 3 eventos
  de esa clase; el registro en BD tiene todos los campos y la imagen abre
  como JPEG.

## Fase 3 — Integración n8n (análisis)

- [x] **T-11 · Envío del evento a n8n** — `integrations/n8n_client.py`: POST a
  `N8N_ANALYSIS_WEBHOOK_URL` con el contrato 3.2 del plan (event_id, fecha,
  clase, confianza, imagen base64, callback_url); ante timeout o error de red,
  marcar el evento `failed` sin reintento. *(RF-4.1, RF-4.3)*
  **Hecho cuando:** al crear un evento se recibe el POST en un receptor de
  prueba con todos los campos; con n8n apagado el evento queda `failed` y
  sigue en BD.

- [x] **T-12 · Webhook de resultado** — `integrations/routes.py`:
  `POST /api/n8n/analysis-result` validando `X-Webhook-Token`; `success`
  guarda `report_text` y marca `done`; `error` marca `failed`; `event_id`
  desconocido se descarta con `404`; respuesta tardía válida actualiza el
  evento aunque estuviera `failed`. *(RF-4.2, RF-4.3)*
  **Hecho cuando:** con curl, cada uno de los 4 casos (éxito, error, id
  desconocido, token inválido → `401`) produce exactamente el estado descrito
  en BD.

## Fase 4 — Panel de reportes

- [x] **T-13 · API de eventos** — `events/routes.py`: `GET /api/events`
  (descendente, `[]` vacío), `GET /api/events/<id>` (JSON con etiquetas en
  español) y `GET /api/events/<id>/image` (JPEG, sesión requerida). *(RF-5.1,
  RF-5.2, RF-5.3, RNF-2)*
  **Hecho cuando:** con curl autenticado los tres endpoints responden según el
  contrato 3.1 del plan; sin cookie devuelven `401`.

- [x] **T-14 · Panel de reportes en el frontend** — `ReportsView.vue`: lista
  descendente con fecha, clase, confianza, estado (realizado/fallido) e
  imagen; detalle con texto del reporte cuando está `done`; estado vacío con
  mensaje en español. *(RF-5.1, RF-5.2, RF-5.3)*
  **Hecho cuando:** con eventos en BD la lista y el detalle se ven completos;
  con BD vacía aparece el mensaje de estado vacío en español.

## Fase 5 — Chatbot

- [x] **T-15 · Proxy de chat en el backend** — `chat/routes.py`:
  `POST /api/chat` reenvía pregunta + `conversation_id` a
  `N8N_CHAT_WEBHOOK_URL` (síncrono) y devuelve `{"answer": ...}`; timeout o
  error → `502` con mensaje en español; nada se persiste. *(RF-6.1, RF-6.3,
  RF-6.4)*
  **Hecho cuando:** con un receptor de prueba, la pregunta llega y la
  respuesta vuelve al cliente; con n8n apagado se recibe `502` con el mensaje
  en español; la BD no tiene tabla ni filas de chat.

- [x] **T-16 · Chatbot en el frontend** — `ChatView.vue`: conversación en
  pantalla (efímera), envío de preguntas, indicador de espera, mensaje de
  error con opción de reintentar. *(RF-6.1, RF-6.3, RF-6.4)*
  **Hecho cuando:** se puede preguntar y ver la respuesta; ante fallo aparece
  el error en español y el botón de reintento funciona; al recargar la página
  la conversación desaparece.

## Fase 6 — Cierre

- [x] **T-17 · Verificación manual de extremo a extremo** — Ejecutar la demo
  completa contra los 7 criterios de finalización de la spec (login,
  transmisión con recuadros y "sin señal", evento con enfriamiento, análisis
  realizado/fallido, panel, chatbot con casos de error). *(todos los RF)*
  **Hecho cuando:** los 7 criterios de finalización de `spec.md` se cumplen en
  una demo continua y los checks de AGENTS.md pasan (`grep openai|yolo` en
  `frontend/` → 0; identificadores en inglés, textos en español).
