# Spec 003: incident reporting

## Contexto y objetivo

Hoy (spec-001) el sistema genera un evento de detección en **cada frame**
donde YOLO detecta un arma con confianza suficiente, y lo envía de inmediato
a n8n para su análisis. Esto genera duplicados cuando el arma permanece
visible varios frames seguidos, y no distingue detecciones puntuales/erróneas
de incidentes reales.

Esta spec introduce una **confirmación temporal** antes de considerar una
detección como candidata a incidencia (el arma debe verse en 3 frames
consecutivos), y delega en el flujo de n8n la decisión final de si se trata
de un **incidente real** o no, mediante un nuevo campo `is_real_incident` en
la respuesta del análisis. Solo si n8n confirma que es real se persiste el
evento en la base de datos. El objetivo es reducir falsos positivos y
duplicados, y dejar registrado únicamente lo que el análisis (YOLO + LLM)
confirma como una amenaza real.

Esta spec **reemplaza** el comportamiento de creación de eventos y envío a
n8n descrito en spec-001 (RF-3 y RF-4): ya no se crea un evento por cada
frame detectado; se crea solo tras la confirmación de 3 frames y la
respuesta positiva de n8n.

## Usuarios

- **Personal de seguridad**: consulta en el panel de reportes únicamente
  incidencias confirmadas como reales, con menos ruido de falsos positivos.

## Requisitos funcionales

### RF-1 — Confirmación por frames consecutivos

- **RF-1.1**: CUANDO el pipeline detecte un arma por primera vez en un
  frame, EL SISTEMA DEBERÁ iniciar un seguimiento de confirmación, sin
  registrar ningún evento todavía.
- **RF-1.2**: MIENTRAS el seguimiento esté activo, EL SISTEMA DEBERÁ exigir
  que los 2 frames inmediatamente siguientes al primero también detecten un
  arma, de forma estrictamente consecutiva (sin frames intermedios sin
  detección).
- **RF-1.3**: SI alguno de los 2 frames siguientes no detecta un arma,
  ENTONCES EL SISTEMA DEBERÁ descartar el seguimiento sin generar evento ni
  enviar nada a n8n. Una detección posterior podrá iniciar un nuevo
  seguimiento desde cero.
- **RF-1.4**: CUANDO los 3 frames consecutivos confirmen la detección, EL
  SISTEMA DEBERÁ tomar la captura del **último (tercer) frame** como la
  evidencia a utilizar en el resto del flujo.
- **RF-1.5**: SI la fuente de video se detiene o se reemplaza mientras un
  seguimiento está en curso (antes de completar los 3 frames), ENTONCES EL
  SISTEMA DEBERÁ descartar el seguimiento sin generar evento.

### RF-2 — Verificación del incidente vía n8n

- **RF-2.1**: CUANDO se confirme una detección (RF-1.4), EL SISTEMA DEBERÁ
  enviar al webhook de análisis de n8n (`N8N_ANALYSIS_WEBHOOK_URL`) un JSON
  con, al menos: la captura del último frame, la clase detectada, el nivel
  de confianza y la fecha/hora, todos correspondientes a ese último frame.
- **RF-2.2**: EL SISTEMA DEBERÁ esperar de forma **síncrona** la respuesta
  del webhook (nodo "Respond to Webhook" del flujo de n8n), que entrega el
  resultado completo del análisis en una sola respuesta al finalizar el
  workflow.
- **RF-2.3**: CUANDO la respuesta de n8n incluya `is_real_incident: true`,
  EL SISTEMA DEBERÁ registrar un evento de incidencia con: fecha/hora,
  imagen, clase, confianza, `report_text`, `suspects_number` y
  `suspects_description`, marcado como análisis **realizado**.
- **RF-2.4**: CUANDO la respuesta de n8n incluya `is_real_incident: false`,
  EL SISTEMA DEBERÁ descartar la detección sin registrar ningún evento ni
  imagen en la base de datos.
- **RF-2.5**: SI el webhook de n8n no responde, responde con error, agota el
  tiempo de espera, o la respuesta no incluye un `is_real_incident` válido
  (booleano), ENTONCES EL SISTEMA DEBERÁ registrar igualmente un evento con
  la captura del último frame, clase, confianza y fecha/hora, marcado como
  análisis **fallido**, sin reporte ni datos de sospechosos.

### RF-3 — Enfriamiento tras un envío a n8n

- **RF-3.1**: CUANDO el sistema envíe una detección confirmada a n8n (sin
  importar si termina en incidencia real, descartada o fallida), EL SISTEMA
  DEBERÁ esperar **15 segundos** antes de permitir el inicio de un nuevo
  seguimiento de confirmación (RF-1.1).
- **RF-3.2**: MIENTRAS dure el enfriamiento de 15 segundos, EL SISTEMA
  DEBERÁ ignorar cualquier nueva detección de arma, sin iniciar seguimiento
  ni registrar nada.

## Datos persistidos

Solo se persiste un evento cuando: (a) n8n confirma `is_real_incident: true`,
o (b) el envío a n8n falla/hace timeout/responde inválido (RF-2.5). En
ambos casos se guarda:

- Fecha y hora del último frame confirmado.
- Captura de imagen del último frame (íntegra, sin difuminado).
- Clase detectada y nivel de confianza (del último frame).
- Estado del análisis: **realizado** o **fallido**.
- `report_text`, `suspects_number` y `suspects_description` (solo cuando el
  análisis fue realizado; vacíos/nulos si fue fallido).

No se persiste nada cuando: el seguimiento se descarta por no confirmarse en
3 frames (RF-1.3), se interrumpe por cambio/caída de fuente (RF-1.5), o n8n
responde `is_real_incident: false` (RF-2.4).

## Casos límite

- Arma visible de forma continua durante varios minutos → cada incidencia
  enviada activa 15 s de enfriamiento antes de volver a evaluar; no hay
  deduplicación adicional más allá de eso.
- El arma desaparece en el 2.º o 3.º frame de la ventana de confirmación →
  se descarta sin generar evento ni tráfico a n8n.
- n8n responde con `is_real_incident` ausente, como texto o `null` → se
  trata como respuesta inválida (RF-2.5, evento fallido).
- n8n tarda más de lo esperado por el análisis LLM y agota el timeout
  configurado → se trata igual que un fallo (RF-2.5).
- La fuente de video cambia o se detiene justo durante la ventana de
  confirmación → se descarta el seguimiento en curso (RF-1.5).
- Reinicio del backend mientras hay un seguimiento en memoria en curso → se
  pierde ese seguimiento (no persistido); comportamiento aceptado, no
  requiere recuperación de estado.

## Fuera de alcance

- Modificar el pipeline de inferencia YOLO existente.
- Modificar el flujo de n8n en sí (se asume que ya expone
  `is_real_incident`, `report_text`, `suspects_number` y
  `suspects_description` en su respuesta final).
- Deduplicación o correlación de incidencias más allá del enfriamiento fijo
  de 15 segundos.
- Persistir capturas o metadata de detecciones descartadas (no confirmadas,
  interrumpidas o marcadas como no reales por n8n).
- Reintento automático ante fallo o timeout del webhook de n8n.
- Notificaciones (Telegram u otro canal): siguen a cargo del flujo de n8n,
  fuera de esta spec.
- Hacer configurable desde la UI el número de frames de confirmación o la
  duración del enfriamiento (son valores fijos de configuración/código).
- Procesar varias detecciones/incidencias en paralelo (solo una activa a la
  vez, ver RF-3).

## Criterios de finalización

1. Una detección de arma que se mantiene en 3 frames consecutivos dispara un
   único envío a n8n con la captura del último frame; si el arma desaparece
   en el 2.º o 3.º frame, no se envía nada ni se registra evento.
2. El envío a n8n espera la respuesta síncrona del nodo "Respond to
   Webhook" antes de continuar.
3. `is_real_incident: true` → se crea un evento consultable en el panel de
   reportes con `report_text`, `suspects_number` y `suspects_description`.
4. `is_real_incident: false` → no queda ningún registro nuevo en la base de
   datos.
5. Fallo, timeout o respuesta inválida de n8n → se crea un evento marcado
   como análisis fallido, con la imagen del último frame pero sin reporte
   ni datos de sospechosos.
6. Tras cada envío a n8n (cualquiera sea el resultado), pasan 15 segundos de
   enfriamiento antes de que una nueva detección pueda iniciar otro
   seguimiento de confirmación.
7. Verificación manual de los puntos 1-6 (con n8n real o un stub que
   simule sus respuestas) confirma el comportamiento de extremo a extremo.

## Dudas abiertas

- Ninguna

