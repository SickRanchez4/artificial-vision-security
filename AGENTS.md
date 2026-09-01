# AGENTS.md — Artificial Vision Security

## Proyecto
App web de seguridad escolar que detecta situaciones de riesgo real (armas de fuego y
armas blancas) mediante cámaras, dentro y fuera de un colegio. Dos capas de IA:
**YOLO** (visión artificial, detección de armas) y **LLM de OpenAI** (análisis de la
captura, generación del reporte y disparo de alarma/notificación). Arquitectura:
backend **Flask** (API REST + toda la lógica), frontend **Vue.js** (solo presentación),
**SQL Server** (persistencia), **n8n** opcional solo si la spec lo justifica.

## Comandos
- Ejecutar backend: `flask --app backend/app run --debug`
- Ejecutar frontend: `npm run dev` (desde `frontend/`)
- Lint/formato: `ruff check . && ruff format .` (backend) · `npm run lint` (frontend)

## Estilo y convenciones
- Python 3.12+ (Flask), Vue 3 con Composition API.
- Identificadores (variables, funciones, clases, tablas): **inglés**.
- Comentarios, docstrings, mensajes de UI, reportes, alertas y commits: **español**.
- Nombres: `snake_case` en Python, `camelCase` en JS, `PascalCase` en componentes Vue.

## Reglas
- Lee `_sdd/constitution.md` y la spec activa (`_sdd/specs/spec.md`) antes de tocar código.
- No implementes funcionalidad que no exista en la spec; si hay que desviarse,
  primero se actualiza la spec.
- No añadas dependencias, frameworks ni servicios fuera del stack fijado
  (Flask, Vue, YOLO, OpenAI, SQL Server, n8n justificado) sin preguntar.
- El frontend nunca llama a YOLO ni a OpenAI ni contiene claves de API; solo
  consume la API REST de Flask.
- Las imágenes capturadas se guardan íntegras (sin difuminar rostros), son datos
  sensibles: acceso por rol, auditoría y purga automática a 30 días.
- Flujo de trabajo: 1 solo dev, sin PRs; los checks se ejecutan localmente antes
  de cada commit a `main`.

## Al terminar cualquier tarea
- Verificar manualmente el flujo afectado contra los criterios de finalización
  de la spec activa.
- Verificar `grep` de `openai`/`yolo` en `frontend/` → 0 resultados.
- Revisar el diff: identificadores en inglés, textos/commits en español, sin
  dependencias nuevas fuera de la spec.