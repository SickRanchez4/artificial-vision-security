# Plan técnico — Spec 004: ai chatbot

Plan técnico de la spec vigente en `spec.md`, alineado con el POC actual:
Flask consulta las incidencias y llama a OpenAI; SQLite local persiste los
datos de la aplicación, incluidos los mensajes de chat; Vue solo consume
la API REST. Sin pruebas automatizadas: la verificación es manual, según
la constitución. La limpieza de reportes añadida en RF-6 es la única
ampliación de este POC.

---

## 1. Estructura de módulos

| Módulo | Responsabilidad | Trazabilidad |
|---|---|---|
| `backend/db.py` | Crear idempotentemente la vista SQLite `incident_summary` sobre `detection_events` (sin `image`) y la tabla `chat_messages` en el archivo local. | RF-1.1, RF-1.2, RF-5.1 |
| `backend/events/repository.py` | Leer todas las filas de la vista para cada petición; no exponer blobs al chat. | RF-1.3 |
| `backend/chat/repository.py` | Guardar mensajes, listar en orden y borrar por `conversation_id` mediante SQLite. | RF-5.1–5.4 |
| `backend/chat/routes.py` | Validar la pregunta y el identificador, llamar a OpenAI con incidencias y pregunta actual, guardar el intercambio exitoso y exponer lectura/borrado del historial. | RF-2.1–2.4, RF-3.1, RF-4.1, RF-5.1–5.4 |
| `backend/config.py` | Obtener la clave de OpenAI desde el entorno; fijar el modelo `gpt-5.4-mini` y el timeout de 30 s. | RF-2.1, RF-4.1 |
| `backend/requirements.txt` | Declarar la librería oficial de Python de OpenAI. | RF-2.1 |
| `frontend/src/views/ChatView.vue` y `frontend/src/services/api.js` | Mostrar el chat, cargar el historial tras recargar, enviar preguntas y ofrecer «Limpiar chat» a través de Flask. | RF-2.2, RF-3.1, RF-4.1, RF-5.2–5.3 |
| `backend/integrations/n8n_client.py` | Mantener el análisis de incidencias vía n8n sin usar su función de chat en esta ruta. | Fuera de alcance |

`backend/app.py` conserva el registro del blueprint y la protección de
sesión existente para `/api/`. No se agregan rutas hacia OpenAI desde Vue
ni cambios en YOLO o en el flujo de análisis de incidencias de spec-003.

## 2. Modelo de datos (SQLite)

El archivo SQLite local del backend, configurado con `SQLITE_DB_PATH`,
contiene `detection_events` y `chat_messages`. `incident_summary` es una
**vista de consulta** sobre `detection_events`, creada con
`CREATE VIEW IF NOT EXISTS` al inicializar la base de datos. No almacena
copias ni modifica eventos.

| Columna de la vista | Origen | Uso |
|---|---|---|
| `detected_at` | `detection_events.detected_at` | Fecha/hora de la incidencia |
| `weapon_class` | `detection_events.weapon_class` | Clase detectada |
| `confidence` | `detection_events.confidence` | Nivel de confianza |
| `analysis_status` | `detection_events.analysis_status` | Estado del análisis |
| `report_text` | `detection_events.report_text` | Reporte textual, si existe |
| `suspects_number` | `detection_events.suspects_number` | Número de sospechosos, si existe |
| `suspects_description` | `detection_events.suspects_description` | Descripción textual, si existe |

No se selecciona `image`; cada lectura recupera todas las incidencias
disponibles, incluidos los registros cuyo análisis falló (con sus campos
de reporte nulos). No se añade filtro ni paginación.

`chat_messages` es una tabla local creada con `CREATE TABLE IF NOT EXISTS`:

| Columna | Tipo y uso |
|---|---|
| `id` | INTEGER, clave primaria autoincremental; orden de los mensajes |
| `conversation_id` | TEXT obligatorio; agrupa el historial visible |
| `role` | TEXT obligatorio; `user` o `assistant` |
| `content` | TEXT obligatorio; pregunta o respuesta |
| `created_at` | TEXT obligatorio; fecha/hora de creación en UTC |

Tras una respuesta válida se insertan la pregunta y la respuesta; ante
fallo del proveedor no se guarda ese intercambio. No se persiste el saludo
inicial ni se crea una tabla separada de conversaciones. El historial se
lee y borra solo por `conversation_id`; el borrado no toca incidencias.
La vista no confiere permisos por sí misma: solo el backend accede a ella;
la protección de imágenes de la constitución corresponde a los mecanismos
generales de eventos, no a este chatbot.

## 3. Contratos de la app

### 3.1 API REST de chat

Se reutiliza la protección de sesión global de `/api/` en Flask (no se
crea un mecanismo de acceso nuevo):

- `POST /api/chat`: recibe JSON con `question` y `conversation_id`, ambos
	obligatorios; pregunta vacía o ID vacío → `400` antes de llamar a
	OpenAI. Si hay respuesta válida → `200` con `{ "answer": "..." }` y
	persiste ambos mensajes de la conversación. Fallo, timeout o respuesta
	vacía → `502` con mensaje genérico; no persiste ese intercambio.
- `GET /api/chat?conversation_id=...`: devuelve
	`{ "messages": [{ "role": "...", "content": "...", "created_at": "..." }] }`
	en orden de inserción. ID vacío → `400`.
- `DELETE /api/chat?conversation_id=...`: elimina las filas de esa
	conversación y devuelve `{ "ok": true }`. ID vacío → `400`.

Vue conserva `conversation_id` en `localStorage` para reutilizar el mismo
historial tras recargar. Al abrir el chat solicita `GET`; «Limpiar chat»
solicita `DELETE` y reinicia la ventana al saludo inicial. El historial se
usa para presentación, no para ampliar el contexto de OpenAI.

### 3.2 Consulta a OpenAI

En cada `POST /api/chat`, el backend recupera la vista completa y envía
**una sola petición** al modelo `gpt-5.4-mini` con el contexto de las
incidencias y la pregunta actual. Cuando la vista está vacía, el contexto
indica explícitamente que no hay incidencias y se realiza igualmente la
petición. No se adjuntan imágenes ni turnos anteriores; el modelo no
genera ni ejecuta SQL. El timeout es de 30 segundos.

Las instrucciones del modelo orientan el uso de los datos para preguntas
sobre incidencias. La aplicación no valida si la pregunta es del tema ni
filtra el contenido de la respuesta.

## 4. Decisiones técnicas justificadas

1. **Vista SQLite, no duplicación de datos:** el contexto refleja los
	eventos existentes sin una tabla adicional (RF-1.1–1.3); la exclusión
	de `image` evita enviar capturas sensibles al proveedor (RF-1.2).
2. **Lectura completa por petición:** garantiza datos actuales sin estado
	adicional ni índices especiales. El crecimiento puede superar el límite
	de contexto o aumentar coste/latencia; se acepta explícitamente en esta
	primera versión, sin truncamiento silencioso ni paginado no autorizados.
3. **Llamada directa desde Flask mediante la librería oficial:** n8n sigue
	siendo responsable del análisis de incidencias de spec-003, pero deja
	de intervenir en el chatbot; se conserva su configuración/función de
	chat sin uso según el fuera de alcance.
4. **Historial persistente sin memoria del modelo:** `conversation_id`
	agrupa los mensajes en SQLite para mostrarlos y borrarlos; solo la
	pregunta actual y los datos de incidencias llegan a OpenAI (RF-2.3,
	RF-5.1–5.3). El ID se conserva en `localStorage` para que el mismo
	navegador recupere su conversación tras recargar.
5. **Persistencia mínima:** el POC guarda un mensaje `user` y uno
	`assistant` tras cada respuesta válida; no guarda un intercambio si
	OpenAI falla (RF-5.1, RF-5.4). `GET`/`DELETE` filtran por ID; no hay
	gestor de conversaciones ni relación de mensajes con usuarios.
6. **Sin nuevas capas de infraestructura:** SQLite local y la librería de
	OpenAI ya usadas; no se incorpora framework de migraciones, servicio
	de chat adicional ni búsqueda vectorial.

## 5. Dependencias previstas

- `openai` (librería oficial de Python; ya declarada en
  `backend/requirements.txt`): necesaria para RF-2.1 y RF-4.1.
- Flask, SQLite (`sqlite3`) y Vue 3: existentes; sin dependencias nuevas
  para el frontend ni servicio n8n adicional para chat.
- `OPENAI_API_KEY`, `OPENAI_CHAT_MODEL` (valor predeterminado
	`gpt-5.4-mini`) y `OPENAI_TIMEOUT_SECONDS` (30 s) son opciones del
	backend. No se documentan valores secretos en este plan.

## 6. Cobertura de requisitos

| Requisito | Decisión / módulo |
|---|---|
| RF-1.1–1.2 | Vista `incident_summary` en `backend/db.py`, proyección sin `image` |
| RF-1.3 | Lectura completa de la vista por petición en `backend/events/repository.py` |
| RF-2.1 | `backend/chat/routes.py`: contexto + pregunta enviados al modelo desde Flask |
| RF-2.2 | `POST /api/chat` devuelve `answer` a Vue |
| RF-2.3 | Petición sin turnos anteriores ni uso de `conversation_id` como memoria |
| RF-2.4 | Contexto explícito cuando la vista no devuelve filas |
| RF-3.1 | Validación de `question` antes de llamar a OpenAI |
| RF-4.1 | Timeout de 30 s y error genérico ante fallo o respuesta vacía |
| RF-5.1 | `chat_messages` en `backend/db.py`, inserción en `backend/chat/repository.py` tras respuesta válida |
| RF-5.2 | `GET /api/chat` y carga de mensajes en `ChatView.vue`; ID en `localStorage` |
| RF-5.3 | `DELETE /api/chat`, borrado por `conversation_id` y botón «Limpiar chat» |
| RF-5.4 | `backend/chat/routes.py` solo inserta después de obtener respuesta válida |

## 7. Verificación manual antes del commit

Sin tests automatizados (constitución, principio 4); comprobar a mano con
la UI, la API y SQLite:

1. Con incidencias reales, verificar que la vista expone exactamente los
	campos de RF-1 y no `image`; comprobar que una pregunta puntual y otra
	agregada devuelven respuestas usando los datos disponibles.
2. Comprobar que la llamada del chat va a OpenAI, modelo `gpt-5.4-mini`,
	sin webhook de n8n ni datos binarios y con la clave solo en el backend.
3. Con vista vacía, preguntar por incidencias: comprobar que se consulta
	al modelo y se comunica que no hay datos.
4. Enviar una pregunta vacía o con espacios: verificar `400` sin llamada
	al proveedor.
5. Provocar error del proveedor, timeout y respuesta vacía: comprobar
	`502` y mensaje genérico visible, sin reintento.
6. Formular dos preguntas consecutivas, siendo la segunda dependiente
	solo de la primera: comprobar que no se transmiten turnos previos como
	contexto (la respuesta del modelo puede variar).
7. Tras una respuesta exitosa, comprobar en SQLite dos filas de
	`chat_messages` con el mismo `conversation_id`, una `user` y otra
	`assistant`; recargar la página y verificar que reaparecen en orden.
8. Provocar un fallo de OpenAI y comprobar que el intercambio fallido no
	aparece en SQLite ni en el historial tras recargar.
9. Pulsar «Limpiar chat», confirmar que se borra solo el historial de la
	conversación actual en SQLite y que los eventos de incidencias siguen
	intactos.
10. Revisar diff, dependencias, idioma de identificadores y mensajes;
    buscar `openai`/`yolo` en `frontend/` (0 resultados). Documentar en el
    commit la verificación manual y los criterios validados.

## 8. Limpieza de reportes (RF-6)

- `backend/events/repository.py`: eliminar en una transacción todas las
	filas de `detection_events`, incluidas las imágenes guardadas como BLOB.
	`incident_summary` queda vacía automáticamente; no se borra el chat.
- `backend/events/routes.py`: exponer `DELETE /api/events` bajo la misma
	sesión de la API para activar el borrado; devolver confirmación sin
	incluir datos sensibles.
- `frontend/src/services/api.js` y `frontend/src/views/ReportsView.vue`:
	confirmar antes de borrar, actualizar el listado y quitar el detalle
	seleccionado solo al recibir éxito; informar errores sin borrar la UI.
- `frontend/src/styles.css` y `frontend/src/views/ChatView.vue`: reutilizar
	una clase visual de botón para «Borrar reportes» y «Limpiar chat», sin
	confundirlos con indicadores de estado.
- Verificación manual: cancelar no envía `DELETE`; confirmar deja vacíos
	el listado y la vista de incidencias, conserva mensajes del chat; un
	fallo de la API mantiene los reportes visibles. Comprobar también la
	apariencia de ambos botones y el acceso con sesión existente.

