# Tareas — Spec 004: ai chatbot

Derivadas de la spec y el plan vigentes. Ordenadas por dependencia: cada
tarea presupone las anteriores. El POC ya contiene parte de esta
funcionalidad, pero las casillas quedan sin marcar hasta comprobar cada
resultado; no se reimplementa lo que ya funcione. No se añaden pruebas
automatizadas ni dependencias fuera del plan: la comprobación es manual.

## Datos locales

- [x] **T-01 · Vista de incidencias en SQLite.** Comprobar o completar en
	`backend/db.py` la creación idempotente de `incident_summary` sobre
	`detection_events` con solo fecha/hora, clase, confianza, estado,
	reporte y datos de sospechosos; excluir `image`.
	**RF:** RF-1.1, RF-1.2.
	**Hecho cuando:** al iniciar con una base SQLite nueva o ya existente,
	la vista expone exactamente esos siete campos, sin `image`, y los datos
	de `detection_events` siguen intactos.

- [x] **T-02 · Lectura completa de incidencias.** Comprobar o completar
	`get_incident_summary()` en `backend/events/repository.py` para leer
	todas las filas de la vista en cada consulta, sin imagen ni paginación.
	**RF:** RF-1.3.
	**Hecho cuando:** una incidencia añadida a SQLite aparece en la siguiente
	lectura y se recupera la cantidad total de filas de la vista.

- [x] **T-03 · Tabla local de mensajes.** Comprobar o completar en
	`backend/db.py` la creación idempotente de `chat_messages` en el mismo
	SQLite, con `id`, `conversation_id`, `role`, `content` y `created_at`.
	**RF:** RF-5.1, RF-5.2, RF-5.3.
	**Hecho cuando:** al reiniciar la aplicación la tabla sigue disponible y
	no se pierden los mensajes ya almacenados.

- [x] **T-04 · Operaciones de mensajes por conversación.** Comprobar o
	completar `save_message()`, `list_messages()` y `clear_messages()` en
	`backend/chat/repository.py`; listar por orden de inserción y borrar
	solo el identificador solicitado.
	**RF:** RF-5.1, RF-5.2, RF-5.3.
	**Hecho cuando:** al guardar mensajes de dos identificadores diferentes,
	ambos se leen en su orden; borrar uno deja intacto el otro y no modifica
	`detection_events`.

## Consulta desde Flask

- [x] **T-05 · Configuración del cliente OpenAI.** Comprobar la
	dependencia oficial `openai` en `backend/requirements.txt` y configurar
	en `backend/config.py` clave solo desde variable de entorno, modelo
	`gpt-5.4-mini` y timeout de 30 segundos; no dejar secretos en código.
	**RF:** RF-2.1, RF-4.1.
	**Hecho cuando:** el backend toma la clave del entorno, usa ese modelo y
	timeout, y no hay ninguna clave real incluida en los archivos del
	proyecto o en el frontend.

- [x] **T-06 · Respuesta independiente y validación.** Comprobar o
	completar `POST /api/chat` en `backend/chat/routes.py`: rechazar pregunta
	vacía antes de consultar al proveedor y enviar una sola petición con la
	pregunta actual y la vista completa; indicar cuando no hay incidencias.
	No enviar mensajes anteriores, imágenes ni usar n8n para el chat.
	**RF:** RF-1.3, RF-2.1, RF-2.3, RF-2.4, RF-3.1.
	**Hecho cuando:** una pregunta vacía devuelve `400` sin llamada; con o
	sin incidencias se llama a OpenAI una sola vez con el contexto correcto,
	sin historial ni imagen.

- [x] **T-07 · Respuesta y errores del proveedor.** Comprobar o completar
	en `POST /api/chat` la entrega de `answer` tras una respuesta válida y
	el error genérico ante excepción, timeout o respuesta vacía, sin
	reintento automático.
	**RF:** RF-2.2, RF-4.1.
	**Hecho cuando:** una respuesta válida llega al cliente como `answer` y
	cada fallo indicado devuelve `502` con un mensaje genérico en español.

- [x] **T-08 · Guardado condicionado al éxito.** Comprobar o completar en
	`POST /api/chat` el guardado de una pregunta `user` y su respuesta
	`assistant` para el mismo `conversation_id` solo después de recibir una
	respuesta válida.
	**RF:** RF-5.1, RF-5.4.
	**Hecho cuando:** una consulta exitosa añade dos filas al historial de
	SQLite y una fallida o vacía no añade ninguna.

- [x] **T-09 · Rutas de lectura y limpieza.** Comprobar o completar
	`GET /api/chat` y `DELETE /api/chat` en `backend/chat/routes.py`, ambas
	por `conversation_id` y bajo la sesión ya exigida por la API.
	**RF:** RF-5.2, RF-5.3.
	**Hecho cuando:** `GET` devuelve los mensajes guardados en orden y
	`DELETE` elimina solo los de ese ID; sin ID ambas rutas devuelven `400`.

## Interfaz y verificación

- [x] **T-10 · Interfaz de chat conectada a Flask.** Comprobar o completar
	`frontend/src/services/api.js` y `frontend/src/views/ChatView.vue` para
	enviar preguntas y presentar respuesta o error, sin acceso directo a
	OpenAI ni claves en el frontend.
	**RF:** RF-2.2, RF-3.1, RF-4.1.
	**Hecho cuando:** desde el chat se muestra la respuesta recibida por la
	API y se muestra el error genérico si el backend devuelve `502`.

- [x] **T-11 · Recarga y limpieza visibles.** Comprobar o completar la
	reutilización del `conversation_id` existente en `localStorage`, la
	carga del historial al abrir el chat y el botón «Limpiar chat» que
	llama al borrado del backend y reinicia la ventana.
	**RF:** RF-5.2, RF-5.3.
	**Hecho cuando:** el historial exitoso reaparece al recargar y, tras
	limpiar, desaparece tanto de la pantalla como de SQLite, sin borrar
	incidencias.

- [x] **T-12 · Verificación manual final.** Recorrer los casos de la
	sección 7 del plan y los criterios de finalización de la spec: datos
	presentes y vacíos, validación, error/timeout, persistencia,
	independencia de preguntas, recarga y limpieza. Revisar diff, idiomas,
	dependencias y ausencia de `openai`/`yolo` en el frontend.
	**RF:** RF-1.1–RF-5.4.
	**Hecho cuando:** cada criterio de finalización tiene un resultado
	comprobado manualmente, la búsqueda en el frontend devuelve cero
	coincidencias y el commit deja constancia de los RF verificados.

- [x] **T-13 · Borrar reportes con confirmación.** Eliminar todas las
	incidencias e imágenes desde SQLite mediante la API existente de
	eventos; añadir confirmación y actualización del panel sin tocar el
	historial del chat. Compartir un estilo de botón con «Limpiar chat».
	**RF:** RF-6.1–RF-6.3.
	**Hecho cuando:** confirmar vacía los reportes y el detalle; cancelar o
	un fallo no borra datos ni el listado visible; ambos botones tienen el
	mismo estilo y el chat permanece intacto.
