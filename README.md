# Seguridad escolar con visión artificial

Aplicación web para monitorear una cámara o un video MP4 y consultar incidencias con evidencia visual. Usa **Vue 3** para la interfaz, **Flask** para la API y el procesamiento, **YOLO** local para detectar armas, **OpenAI** para analizar capturas y responder consultas, y **SQLite** para guardar reportes e historial del chat.

## Flujo

1. YOLO analiza el video localmente y señala posibles armas.
2. Tras confirmar la detección en frames consecutivos, Flask envía la captura a OpenAI para decidir si corresponde a una incidencia real y generar un reporte en español.
3. Las incidencias confirmadas se guardan con su imagen en SQLite y aparecen en la pestaña de reportes; las descartadas no se guardan. Si falla el análisis, se conserva la captura como análisis fallido.
4. El chatbot permite consultar los datos de los reportes guardados. No hay notificaciones externas implementadas.

**¿Por qué dos modelos?** YOLO filtra el video en el equipo sin enviar cada frame a un servicio externo; OpenAI analiza solo las capturas candidatas para dar contexto y reducir falsos positivos. Así se limita el tráfico de imágenes, aunque el análisis generativo no sustituye la revisión humana.

El modelo YOLO de detección de armas de fuego se entrenó en este [proyecto de Kaggle](https://www.kaggle.com/code/rastone/train-yolov8-weapon-detection-cctv/).

## Ejecutar en Windows (PowerShell)

Requisitos: Python 3.12+, Node.js 20.19+ y Git. Desde la raíz del repositorio, abrir **dos terminales**.

**Terminal 1 — backend:**

```powershell
cd backend
python -m venv _venv
.\_venv\Scripts\python.exe -m pip install -r requirements.txt
$env:OPENAI_API_KEY = "tu-clave-de-openai"
.\_venv\Scripts\python.exe app.py
```

El archivo del modelo debe estar en `backend/yolov8s-security.pt` (o indicar su ruta con `YOLO_MODEL_PATH`). Los modelos de imagen y chat se pueden elegir mediante `OPENAI_IMAGE_MODEL` y `OPENAI_CHAT_MODEL`; ambos tienen `gpt-5.4-mini` como valor predeterminado en la configuración actual. Usa nombres de modelo exactos y habilitados para tu cuenta.

**Terminal 2 — frontend:**

```powershell
cd frontend
npm install
npm run dev
```

Abrir la dirección que muestre Vite (normalmente `http://localhost:5173`). El frontend redirige las peticiones a la API de Flask en `http://localhost:5000`. Inicia sesión y selecciona un MP4 o una cámara en la pestaña de transmisión.
