# Tareas — Spec 005: opeanai image analysis

Derivadas de la spec y el plan vigentes. Ordenadas por dependencia: cada
tarea presupone las anteriores. No se añaden pruebas
automatizadas ni dependencias fuera del plan: la comprobación es manual.

## Tareas

- [x] **T-01 · Eliminar lo referente al flujo de n8n para el análisis de imagen.** Quitar n8n del análisis de imagen.
	**RF:** RF-4.
	**Hecho cuando:** no quede ninguna referencia a n8n en el análisis de imagen.

- [x] **T-02 · Implementar el nuevo flujo de análisis de imagen.** CConectar la entrada de imagen con la API de OpenAI. Gestionar respuesta, error y timeout.
	**RF:** RF-1, RF-2, RF-3.
	**Hecho cuando:** una imagen se analiza correctamente usando OpenAI.

- [x] **T-03 · Verificación manual final.** Probar casos válidos, vacíos, error, timeout, persistencia y recarga. Revisar que no queden restos de n8n ni dependencias innecesarias.
	**RF:** RF-1, RF-2, RF-3, RF-4.
	**Hecho cuando:** cada criterio de finalización tiene un resultado
	comprobado manualmente, la búsqueda en el frontend devuelve cero
	coincidencias y el commit deja constancia de los RF verificados.
