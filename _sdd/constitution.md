# Constitución — Sistema de Visión Artificial para Seguridad Escolar

Principios innegociables del proyecto. Toda decisión de diseño, código o infraestructura
debe cumplirlos. Si un cambio los contradice, primero se modifica esta constitución.

> Flujo de trabajo: **1 solo desarrollador, sin Pull Requests.** Las verificaciones se
> hacen con checks locales (revisión del diff, grep) antes de cada commit a `main`.

## 1. Simplicidad del stack

- El stack es exactamente: **Flask** (backend), **Vue.js** (frontend), **YOLO** (detección),
  **OpenAI** (reportes/alertas), **SQLite** (datos). **n8n** solo si un flujo lo
  justifica por escrito en la spec.
- Prohibido añadir frameworks, librerías o servicios no listados en la spec activa
  sin actualizar primero la spec.
- ✅ *Verificable:* toda dependencia en `requirements.txt` / `package.json` está trazada
  a una sección de la spec.

## 2. La spec manda sobre el código

- No se escribe código de una funcionalidad que no exista en `_sdd/specs/spec.md`.
- Si el código necesita desviarse de la spec, primero se modifica la spec, luego el código.
- ✅ *Verificable:* cada commit de funcionalidad referencia en su mensaje la sección
  de la spec que implementa.

## 3. Separación lógica / interfaz

- La lógica de detección (YOLO), análisis (LLM) y alertas vive **solo en el backend**
  (Flask). Vue solo presenta datos y captura interacción.
- El frontend nunca llama directamente a YOLO ni a OpenAI; solo consume la API REST
  de Flask.
- ✅ *Verificable:* cero claves de API o modelos en el frontend; `grep` de
  `openai`/`yolo` en `frontend/` devuelve 0 resultados.

## 4. Verificación manual

- El proyecto **no incluye tests automatizados**. Toda funcionalidad se valida con
  una verificación manual de extremo a extremo contra los criterios de finalización
  de la spec activa antes de commitear a `main`.
- La lógica crítica de seguridad (clasificación de riesgo, disparo de alarma) se
  verifica manualmente con casos positivos, negativos y falsos positivos.
- ✅ *Verificable:* el mensaje de commit indica que la verificación manual se realizó
  y contra qué criterios de la spec.

## 5. Persistencia de datos

- Base de datos: **SQLite** desde el inicio (archivo local del backend, sin
  servicio externo). Nada se guarda solo en memoria.
- Todo evento de detección se persiste con: timestamp, imagen/captura, clase detectada,
  confianza, reporte del LLM y estado de la alerta.
- Las imágenes se conservan **íntegras y sin distorsión de rostros**: la identificación
  de las personas involucradas es parte del propósito de seguridad del sistema.
- Como contrapartida, las imágenes son **datos sensibles**: acceso restringido por rol,
  registro de auditoría de cada consulta y retención máxima de **30 días**, tras los
  cuales se eliminan automáticamente (salvo evidencia marcada para investigación activa).
- ✅ *Verificable:* cada detección genera un registro consultable en BD; existe un job
  de purga a 30 días; no hay ningún paso de difuminado/pixelado en el pipeline.

## 6. Idioma del código y los mensajes

- Identificadores del código (variables, funciones, clases, tablas): **inglés**.
- Comentarios, docstrings, mensajes de UI, reportes generados, alertas y mensajes
  de commit: **español**.
- ✅ *Verificable:* una revisión rápida del diff antes de commitear no encuentra
  identificadores en español ni textos de UI en inglés.