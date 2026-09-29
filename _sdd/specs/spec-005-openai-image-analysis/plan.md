# Plan técnico — Spec 005

1. Reutilizar la librería `openai` ya declarada: enviar el JPEG como
   `image_url` con data URI base64 a Chat Completions y solicitar JSON.
   Validar la respuesta antes de entregarla al pipeline; `None` señala
   un fallo. Modelo independiente `OPENAI_IMAGE_MODEL=gpt-4o` y timeout
   compartido con el chat; nunca registrar la imagen ni la clave.
2. Mantener en el pipeline la decisión existente de persistencia:
   `true` → evento completo; `false` → descarte; `None` → evento fallido.
   No modificar el tracker ni las rutas de eventos.
3. Eliminar los webhooks, el cliente y el blueprint de n8n que ya no se
   utilizan, y retirar `requests` como dependencia directa. Corregir
   comentarios desactualizados. Sin cambios en Vue ni en SQLite.
4. Verificar manualmente los tres resultados y los errores con respuestas
   simuladas y una base SQLite temporal; revisar que no quede código
   ejecutable de n8n ni referencias a OpenAI/YOLO en Vue.