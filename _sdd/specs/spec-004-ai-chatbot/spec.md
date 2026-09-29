# Spec 004: ai chatbot

## Contexto y objetivo

El panel de reportes (spec-003) permite ver las incidencias una por una,
pero no permite hacer preguntas agregadas o de lenguaje natural sobre ellas
("¿cuántas incidencias hubo esta semana?", "¿qué reportó el último
incidente?"). Esta spec añade un chatbot que responde ese tipo de preguntas
usando el servicio de OpenAI (modelo `gpt-5.4-mini`) con acceso de solo
lectura a los datos de incidencias ya persistidos en SQLite local.

Existía una implementación previa del chat que delegaba la pregunta a un
webhook de n8n (`N8N_CHAT_WEBHOOK_URL` / `ask_chat`). Esta spec **reemplaza
por completo** ese mecanismo: el backend deja de llamar a n8n para el chat
y en su lugar llama directamente a la API de OpenAI usando su librería
oficial de Python.

El enfoque para esta primera versión es deliberadamente simple: por cada
pregunta, el backend arma un contexto con **todos** los datos relevantes de
incidencias (vía una vista de solo lectura de la base de datos) y se lo
envía junto con la pregunta del usuario a OpenAI en una sola llamada. No
hay memoria en las consultas al modelo ni generación de SQL por parte de
este: solo recibe datos de incidencias y la pregunta actual. El historial
visible de preguntas y respuestas se guarda por conversación en la misma
base de datos SQLite local, para poder recuperarlo tras recargar la página
y borrarlo desde el chat; nunca se envía al modelo como contexto.

## Usuarios

- **Personal de seguridad**: hace preguntas en lenguaje natural sobre el
  historial de incidencias registradas, sin necesidad de revisar el panel
  de reportes manualmente.

## Requisitos funcionales

### RF-1 — Vista de incidencias para el chatbot

- **RF-1.1**: EL SISTEMA DEBERÁ exponer en la base de datos una vista de
  solo lectura con los datos de incidencias relevantes para responder
  preguntas: fecha/hora, clase detectada, confianza, estado del análisis,
  `report_text`, `suspects_number` y `suspects_description`.
- **RF-1.2**: La vista NO DEBERÁ incluir la imagen binaria de cada
  incidencia (es un dato sensible y no aporta a una respuesta en texto).
- **RF-1.3**: EL SISTEMA DEBERÁ leer esta vista completa (sin límite de
  cantidad de filas) cada vez que se recibe una pregunta, reflejando
  siempre el estado más reciente de la base de datos.

### RF-2 — Consulta al chatbot

- **RF-2.1**: CUANDO el usuario envíe una pregunta al endpoint de chat, EL
  SISTEMA DEBERÁ construir una sola llamada al servicio de OpenAI (modelo
  `gpt-5.4-mini`) que incluya: los datos completos de la vista de
  incidencias (RF-1) como contexto, y la pregunta del usuario.
- **RF-2.2**: EL SISTEMA DEBERÁ devolver al usuario la respuesta en
  lenguaje natural generada por el modelo, sin procesamiento adicional del
  contenido.
- **RF-2.3**: Cada pregunta se procesa de forma **independiente**: EL
  SISTEMA NO DEBERÁ reutilizar preguntas o respuestas anteriores como
  contexto de una nueva pregunta al modelo, aunque estén persistidas para
  mostrarlas en la interfaz.
- **RF-2.4**: SI la base de datos no tiene ninguna incidencia registrada
  todavía, ENTONCES EL SISTEMA DEBERÁ indicárselo explícitamente al modelo
  como parte del contexto (en vez de omitir la llamada), para que la
  respuesta refleje que no hay incidencias.

### RF-3 — Validación de la pregunta

- **RF-3.1**: SI la pregunta recibida está vacía o contiene solo espacios
  en blanco, ENTONCES EL SISTEMA DEBERÁ rechazarla con un error, sin llamar
  a OpenAI.

### RF-4 — Manejo de errores del servicio OpenAI

- **RF-4.1**: SI la llamada a OpenAI falla, responde con error, agota el
  tiempo de espera (30 segundos) o devuelve una respuesta vacía, ENTONCES
  EL SISTEMA DEBERÁ responder al usuario con un mensaje de error genérico
  indicando que el asistente no está disponible, sin reintento automático.

### RF-5 — Historial local del chat

- **RF-5.1**: CUANDO OpenAI devuelva una respuesta válida, EL SISTEMA
  DEBERÁ guardar la pregunta y la respuesta como dos mensajes asociados
  al identificador de conversación en la base de datos SQLite local.
- **RF-5.2**: CUANDO el usuario vuelva a abrir o recargue el chat, EL
  SISTEMA DEBERÁ recuperar y mostrar en orden los mensajes guardados para
  ese identificador de conversación.
- **RF-5.3**: CUANDO el usuario pulse «Limpiar chat», EL SISTEMA DEBERÁ
  eliminar de SQLite los mensajes asociados a esa conversación y vaciar
  el historial mostrado en la ventana de chat.
- **RF-5.4**: SI OpenAI falla o devuelve una respuesta vacía, ENTONCES EL
  SISTEMA NO DEBERÁ guardar esa pregunta ni una respuesta en el historial
  de la base de datos.

### RF-6 — Limpieza manual de reportes

- **RF-6.1**: CUANDO el usuario solicite borrar los reportes desde la
  pestaña de reportes y confirme la acción, EL SISTEMA DEBERÁ eliminar
  todos los registros de incidencias y sus capturas de SQLite.
- **RF-6.2**: SI el usuario cancela la confirmación o falla el borrado,
  ENTONCES EL SISTEMA NO DEBERÁ vaciar el listado visible ni eliminar
  mensajes del chat u otros datos de la aplicación.
- **RF-6.3**: CUANDO se complete el borrado, EL SISTEMA DEBERÁ mostrar el
  estado sin reportes y dejar de mostrar el detalle de la incidencia
  seleccionada. El botón de borrado y el de «Limpiar chat» DEBERÁN
  compartir un estilo de botón claramente accionable.

## Datos persistidos

La base de datos es un archivo SQLite local del backend. Se reutiliza
`detection_events` (spec-003) y se añade una vista de solo lectura sobre
esa tabla (RF-1.1), sin copiar ni modificar sus incidencias.

Los mensajes del chat se guardan en `chat_messages` con identificador de
conversación, tipo de mensaje (`user` o `assistant`), contenido y fecha/hora
de creación. El identificador permite recuperar y borrar los mensajes de
la conversación visible; se conserva en el navegador al recargar la
página. Solo se persisten preguntas que obtuvieron respuesta válida y sus
respuestas (RF-5.1, RF-5.4). El saludo inicial de la interfaz no se guarda.

Al borrar reportes se eliminan las filas de `detection_events`, incluida
la imagen almacenada en cada una. No se eliminan filas de `chat_messages`:
el historial previo del chat sigue disponible, aunque las preguntas nuevas
consulten la vista de incidencias ya vacía.

## Casos límite

- No hay ninguna incidencia registrada aún → se informa al modelo que la
  vista está vacía y la respuesta lo refleja (RF-2.4), sin error.
- Pregunta vacía o solo espacios → error 400 sin llamar a OpenAI (RF-3.1).
- OpenAI no responde, responde con error o agota el timeout de 30s → se
  muestra un mensaje de error genérico al usuario (RF-4.1) y no se guarda
  ese intercambio en SQLite (RF-5.4).
- Recargar la página tras una respuesta exitosa → reaparecen los mensajes
  guardados para la conversación actual (RF-5.2).
- Limpiar el chat → se eliminan de SQLite solo los mensajes de esa
  conversación; los incidentes de `detection_events` no se alteran
  (RF-5.3).
- Borrar reportes con confirmación → desaparecen todas las incidencias y
  capturas; cancelar o sufrir un error deja visible el listado anterior.
- Incidencias generadas después del borrado → vuelven a aparecer al
  actualizar la pestaña de reportes.
- El usuario pregunta algo sin relación con las incidencias → no se añade
  validación del tema; el resultado depende de las instrucciones enviadas
  al modelo y no se filtra en la aplicación.
- La tabla de incidencias crece con el tiempo → no hay límite ni paginado
  en esta spec; se envía siempre el contenido completo de la vista.

## Fuera de alcance

- Memoria conversacional del modelo: el historial persistido se usa para
  mostrar el chat, no para responder a nuevas preguntas (RF-2.3).
- Generación de SQL o acceso directo del modelo a la base de datos: solo
  recibe las incidencias ya extraídas; el backend es quien guarda y borra
  los mensajes del chat.
- Persistir mensajes adicionales al intercambio exitoso (por ejemplo,
  el saludo inicial o preguntas sin respuesta válida).
- Validar el tema de las preguntas o filtrar el contenido de las
  respuestas del modelo.
- Límite de tamaño, paginado o resumen de los datos de incidencias enviados
  al modelo cuando la tabla crezca mucho.
- Reintento automático ante fallo o timeout de OpenAI.
- Autenticación o restricción de acceso adicional al endpoint de chat más
  allá de lo que ya exista en la app.
- Eliminar del código la configuración `N8N_CHAT_WEBHOOK_URL` ni la función
  `ask_chat` de n8n_client.py: quedan sin uso, pero no se remueven en esta
  spec.
- Modificar el flujo de n8n de análisis de incidencias (`verify_incident`,
  spec-003): sigue vigente y sin cambios.
- Borrado selectivo de incidencias individuales y nuevas reglas de
  retención o marcado de investigaciones activas (no hay tal marca en el
  modelo actual).

## Criterios de finalización

1. Existe una vista de solo lectura en la base de datos con los datos de
   incidencias relevantes (sin la imagen binaria) y el chatbot la usa como
   contexto en cada pregunta.
2. Al hacer una pregunta al chatbot, el backend llama directamente a la
   API de OpenAI (modelo `gpt-5.4-mini`) con ese contexto y la pregunta, sin
   pasar por n8n.
3. Con incidencias registradas, el chatbot responde en lenguaje natural
   preguntas agregadas o puntuales usando esos datos (por ejemplo, cantidad
   de incidencias, contenido de `report_text` o `suspects_description`).
4. Sin ninguna incidencia registrada, el chatbot responde reflejando que no
   hay datos, sin error.
5. Una pregunta vacía se rechaza sin llamar a OpenAI.
6. Un fallo, timeout o respuesta vacía de OpenAI se traduce en un mensaje
   de error genérico visible en el frontend.
7. Tras obtener una respuesta válida, pregunta y respuesta aparecen como
   mensajes asociados a la conversación en SQLite y vuelven a mostrarse al
   recargar la página; una pregunta fallida no queda guardada.
8. «Limpiar chat» borra de SQLite el historial de la conversación visible
   y limpia la ventana sin borrar incidencias.
9. Preguntas consecutivas no comparten contexto ante OpenAI: solo se envía
   la pregunta actual y la vista de incidencias, no el historial guardado.
10. Verificación manual de los puntos 1-9 contra la spec, con datos reales
    en la base de datos.
11. Tras confirmar «Borrar reportes», no quedan filas ni imágenes de
  incidencias en SQLite y el panel muestra su estado vacío; el chat
  persiste. Cancelar o provocar un fallo deja intactos los datos.
12. «Borrar reportes» y «Limpiar chat» tienen el mismo estilo visual de
  botón de acción y son distinguibles de indicadores de estado.

## Dudas abiertas

- Ninguna

