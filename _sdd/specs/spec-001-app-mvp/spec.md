# Spec 001 — MVP: Monitoreo, reportes y chatbot de seguridad

## Contexto y objetivo

Un colegio necesita detectar situaciones de riesgo real (armas de fuego y armas
blancas) a partir de una cámara de vigilancia, y dejar constancia de cada evento
con evidencia visual y un reporte analizado. El MVP demuestra el flujo completo
de extremo a extremo: **ver la transmisión → detectar un arma → registrar el
evento con su captura → recibir el reporte analizado y la notificación → poder
consultar el historial en lenguaje natural**.

El análisis con IA generativa y la notificación externa (Telegram) los realiza
un flujo de n8n **ya existente y operativo**: esta app solo le envía datos y
recibe resultados. Construir o modificar ese flujo queda fuera de esta spec.

> **Desviación declarada de la constitución (principio 4):** este MVP se
> desarrolla **sin tests automatizados** en ningún aspecto. La política de
> tests se retomará en una spec posterior.

## Usuarios

- **Personal de seguridad** (rol único del MVP): inicia sesión, observa la
  transmisión, revisa los reportes y consulta el historial vía chatbot.

## Historias de usuario

- **HU-1** — Como personal de seguridad, quiero ver la transmisión de la cámara
  en vivo para vigilar la zona sin estar físicamente presente.
- **HU-2** — Como personal de seguridad, quiero que el sistema detecte armas de
  fuego y armas blancas automáticamente para no depender de mi atención continua.
- **HU-3** — Como personal de seguridad, quiero que cada detección quede
  registrada con su captura y un reporte analizado, para tener evidencia y
  contexto de lo ocurrido.
- **HU-4** — Como personal de seguridad, quiero revisar los reportes en un panel
  para evaluar los eventos pasados.
- **HU-5** — Como personal de seguridad, quiero preguntarle a un chatbot sobre
  los reportes registrados para obtener respuestas sin buscar manualmente.

## Requisitos funcionales

### RF-1 — Autenticación
- **RF-1.1**: CUANDO un usuario no autenticado intente acceder a cualquier
  vista o dato de la app, EL SISTEMA DEBERÁ redirigirlo al inicio de sesión.
- **RF-1.2**: CUANDO un usuario ingrese credenciales válidas, EL SISTEMA DEBERÁ
  darle acceso a las tres pestañas (transmisión, reportes, chatbot).
- **RF-1.3**: CUANDO un usuario ingrese credenciales inválidas, EL SISTEMA
  DEBERÁ mostrar un mensaje de error en español sin revelar qué campo falló.

### RF-2 — Transmisión en vivo
- **RF-2.1**: MIENTRAS la fuente de video esté disponible, EL SISTEMA DEBERÁ
  mostrar la transmisión en la pestaña correspondiente. La fuente del MVP es
  un video pregrabado reproducido en bucle que simula una cámara.
- **RF-2.2**: CUANDO la fuente de video no esté disponible, EL SISTEMA DEBERÁ
  mostrar el estado "cámara sin señal" y el resto de la app DEBERÁ seguir
  operando con normalidad.
- **RF-2.3**: CUANDO se detecte un arma en el video, EL SISTEMA DEBERÁ indicar
  visualmente la detección sobre la transmisión (p. ej. recuadro sobre el objeto).

### RF-3 — Detección y registro de eventos
- **RF-3.1**: CUANDO aparezca un arma de fuego o un arma blanca en el video
  con una confianza igual o superior al **70 %**, EL SISTEMA DEBERÁ generar
  un evento de detección. Las detecciones por debajo del umbral se descartan.
- **RF-3.2**: CUANDO se genere un evento de detección, EL SISTEMA DEBERÁ
  persistir: fecha y hora, captura de imagen íntegra (sin difuminar rostros),
  clase detectada (arma de fuego / arma blanca), nivel de confianza y estado
  del análisis.
- **RF-3.3**: MIENTRAS exista un evento de la misma clase creado en los
  últimos **20 segundos**, EL SISTEMA NO DEBERÁ crear un nuevo evento de esa
  clase (enfriamiento anti-inundación).

### RF-4 — Análisis y notificación (vía n8n)
- **RF-4.1**: CUANDO se cree un evento de detección, EL SISTEMA DEBERÁ enviar
  al flujo externo de análisis (n8n): el **identificador del evento**, la
  **fecha y hora**, la **clase detectada**, el **nivel de confianza** y la
  **captura de imagen**. El flujo externo analiza la imagen con IA generativa
  y envía la notificación por Telegram.
- **RF-4.2**: CUANDO el flujo externo devuelva su resultado — **identificador
  del evento**, **texto del reporte en español** y **resultado del análisis
  (éxito/error)** —, EL SISTEMA DEBERÁ guardar el texto asociado al evento y
  marcar el análisis como **realizado**.
- **RF-4.3**: SI el flujo externo no responde, devuelve error o el
  identificador no corresponde a ningún evento, ENTONCES EL SISTEMA DEBERÁ
  conservar el evento igualmente y marcar el análisis como **fallido**.
  No hay reintento automático en el MVP.

### RF-5 — Panel de reportes
- **RF-5.1**: CUANDO el usuario abra la pestaña de reportes, EL SISTEMA DEBERÁ
  listar los eventos ordenados del más reciente al más antiguo, mostrando por
  cada uno: fecha y hora, clase detectada, confianza, estado del análisis
  (realizado/fallido) y la imagen que originó el reporte.
- **RF-5.2**: CUANDO el usuario seleccione un reporte, EL SISTEMA DEBERÁ
  mostrar el detalle completo, incluido el texto del reporte analizado cuando
  el análisis esté realizado.
- **RF-5.3**: CUANDO no existan reportes, EL SISTEMA DEBERÁ mostrar un estado
  vacío con mensaje en español.

### RF-6 — Chatbot sobre reportes
- **RF-6.1**: CUANDO el usuario envíe una pregunta en la pestaña de chatbot,
  EL SISTEMA DEBERÁ remitir al flujo externo (n8n) la **pregunta en texto**
  junto con un **identificador de conversación**; el flujo consulta los datos
  de reportes y devuelve la **respuesta en texto**, que EL SISTEMA DEBERÁ
  mostrar en la conversación.
- **RF-6.2**: El chatbot DEBERÁ responder únicamente sobre los reportes
  registrados; ante preguntas fuera de ese ámbito DEBERÁ indicar que solo
  puede responder sobre los reportes.
- **RF-6.3**: SI el flujo externo no responde, ENTONCES EL SISTEMA DEBERÁ
  mostrar un mensaje de error en español y permitir reintentar la pregunta.
- **RF-6.4**: Los mensajes del chatbot son efímeros: se muestran durante la
  sesión en pantalla y **no se persisten** como parte de los datos del sistema.

## Datos persistidos

Los datos se conservan en **SQL Server**. Por cada **evento de detección** se conserva:
- Identificador único del evento.
- Fecha y hora de la detección.
- Captura de imagen íntegra (sin difuminado de rostros).
- Clase detectada (arma de fuego / arma blanca).
- Nivel de confianza de la detección.
- Estado del análisis: **pendiente → realizado / fallido**.
- Texto del reporte generado por el análisis externo (solo si fue realizado).

No se persisten: los frames de video sin detección, las detecciones por debajo
del umbral de confianza, ni las conversaciones del chatbot.

## Requisitos no funcionales

- **RNF-1**: Todos los textos de la interfaz, reportes, alertas y mensajes de
  error estarán en español.
- **RNF-2**: Las capturas se almacenan íntegras, sin distorsión de rostros, y
  solo son accesibles para usuarios autenticados.
- **RNF-3**: El tiempo entre la detección y la aparición del evento en el panel
  de reportes (sin contar el análisis externo) no debe superar los
  **5 segundos**, exigencia acorde a un entorno de demostración.
- **RNF-4**: La caída de cualquier dependencia externa (fuente de video, flujo
  n8n) no debe impedir el uso del resto de la app.

## Casos límite

- Arma visible de forma continua durante minutos → el enfriamiento de 20 s
  evita eventos duplicados (RF-3.3).
- Dos clases distintas visibles a la vez (pistola + cuchillo) → se genera un
  evento por clase, cada una con su propio enfriamiento.
- n8n responde tarde (después del enfriamiento o de mucho tiempo) → la
  respuesta se asocia al evento original mediante su identificador; no crea
  un evento nuevo.
- n8n responde con un identificador de evento desconocido → se descarta la
  respuesta y no se altera ningún evento (RF-4.3).
- Video en bucle: al reiniciar el bucle se vuelve a “ver” la misma arma → se
  trata como detección normal sujeta a enfriamiento; no hay deduplicación
  por contenido.
- Detección con confianza exactamente en 70 % → se considera válida (umbral
  inclusivo).
- Pregunta al chatbot cuando no hay ningún reporte → respuesta indicando que
  no hay registros, no un error.
- Sesión expirada mientras se ve la transmisión → redirección al login sin
  pérdida de eventos (la detección corre en el servidor, no en el navegador).

## Fuera de alcance (MVP)

- Construcción o modificación del flujo de n8n (análisis LLM, Telegram): se
  asume existente y operativo.
- Tests automatizados de cualquier tipo
- Purga automática de imágenes a 30 días y auditoría de accesos
  (**desviación temporal de la constitución, principio 5**; se abordará en
  una spec posterior antes de operar con datos reales).
- Múltiples cámaras o fuentes simultáneas.
- Múltiples roles o gestión de usuarios (altas/bajas).
- Reintento automático de análisis fallidos.
- Persistencia del historial del chatbot.
- Detección de otras clases de riesgo (peleas, intrusiones, etc.).
- Notificaciones por canales distintos de los que ya gestione n8n.

## Criterios de finalización

1. Un usuario puede iniciar sesión, y sin sesión no se accede a nada.
2. La pestaña de transmisión muestra el video en bucle con las detecciones
   marcadas, y muestra "cámara sin señal" si la fuente falla.
3. Al aparecer un arma con confianza ≥ 70 % se crea un evento con captura,
   clase, confianza y timestamp, respetando el enfriamiento de 20 s.
4. El evento enviado a n8n vuelve con su reporte y queda como "realizado";
   si n8n falla, el evento queda como "fallido" y sigue visible.
5. El panel de reportes lista y detalla los eventos con su imagen.
6. El chatbot responde preguntas sobre los reportes registrados y maneja el
   caso "sin reportes" y el fallo de n8n con mensajes claros en español.
7. Verificación manual de los puntos 1-6 en una demo de extremo a extremo.

## Dudas abiertas

- Ninguna por el momento.