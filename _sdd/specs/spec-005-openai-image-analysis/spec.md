# Spec 005: análisis de capturas con OpenAI

Esta spec reemplaza exclusivamente la verificación vía n8n de la spec-003
(RF-2 y referencias de RF-3 al envío a n8n). La confirmación temporal,
el enfriamiento, YOLO, la persistencia y la interfaz siguen como están.
El chat continúa usando su propio modelo configurado en spec-004.

## Requisitos

- **RF-1:** Tras confirmar la detección, el backend envía el JPEG íntegro
  del último frame y la clase, confianza y fecha/hora a OpenAI con el
  modelo `gpt-4o` por defecto, configurable mediante
  `OPENAI_IMAGE_MODEL`. La clave procede de `OPENAI_API_KEY` y el timeout
  de `OPENAI_TIMEOUT_SECONDS`; no llegan claves ni llamadas a Vue.
- **RF-2:** La respuesta del modelo debe ser JSON con
  `is_real_incident` booleano y, para incidencias reales, un
  `report_text` no vacío en español; se admiten `suspects_number` y
  `suspects_description` cuando la imagen permita determinarlos, sin
  inventar datos. Si el incidente es real, se guarda el evento con
  captura y reporte; si es falso, no se guarda.
- **RF-3:** Ante clave ausente, error, timeout, respuesta vacía, JSON
  inválido o campos obligatorios inválidos, se registra el evento con
  imagen y estado `failed`, sin reporte ni datos de sospechosos; no hay
  reintentos automáticos. La solicitud se espera en el hilo de análisis
  sin bloquear la captura de frames.
- **RF-4:** Se retira la integración de n8n de análisis y la configuración,
  cliente y rutas de n8n que han quedado sin uso (incluida la función de
  chat ya reemplazada en spec-004). No se añade otro servicio ni se
  implementan notificaciones externas; las antiguas notificaciones de
  n8n dejan de enviarse.

## Verificación manual

Con una base de datos temporal, comprobar respuestas simuladas del cliente
OpenAI para caso real, falso, fallo de proveedor y respuesta inválida;
verificar imagen, datos y estado en SQLite. Comprobar que el JPEG y los
metadatos van a `gpt-4o` por defecto, que la configuración permite cambiar
el modelo y que no quedan llamadas a n8n. Para probar el modelo real
se requiere clave válida y una captura de prueba, sin usar imágenes
sensibles reales ni alterar la base de datos local del usuario.

## Fuera de alcance

- Cambiar el umbral de YOLO, el número de frames de confirmación o los
  15 segundos de enfriamiento.
- Crear un canal nuevo de alertas o notificaciones externas.
- Cambiar el modelo o el flujo del chatbot.