# Spec 002 — video source

## Contexto y objetivo

La aplicación de visión artificial para seguridad necesita poder analizar video proveniente de distintos orígenes con el motor de detección YOLO. Esta spec define la incorporación de dos fuentes de video: **archivo cargado (.mp4)** y **cámara del dispositivo**.

El objetivo es **desacoplar el origen del video del motor de inferencia YOLO**, de modo que el módulo de detección reciba frames de forma homogénea sin importar de dónde provienen. La inferencia YOLO ya corre en el backend y está implementada; esta spec se enfoca exclusivamente en la capa de **ingestión** de video desde las dos fuentes, sin modificar el pipeline de inferencia existente.

## Usuarios

- **Operador de seguridad**: selecciona la fuente de video y visualiza las detecciones en tiempo real o sobre el video cargado.
- **Administrador del sistema**: da soporte/configura el acceso a las cámaras usadas por los operadores.
- **Desarrollador/integrador**: consume la abstracción de fuente de video para conectar nuevas fuentes a futuro sin tocar el motor de detección.

## Requisitos funcionales

**RF-1.** El sistema debe permitir seleccionar el tipo de fuente de video entre: archivo local (.mp4) y cámara del dispositivo. Solo una fuente puede estar activa a la vez.

**RF-2. Fuente archivo (.mp4)**
- RF-2.1 El usuario debe poder cargar un archivo .mp4 desde su dispositivo.
- RF-2.2 El sistema debe validar la extensión .mp4 y rechazar archivos que superen **256 MB**.
- RF-2.3 El sistema debe mostrar un indicador de progreso durante la subida del archivo.
- RF-2.4 El sistema debe permitir reproducir el archivo con controles básicos (play/pause/seek) mientras se ejecuta el análisis.
- RF-2.5 El archivo se descarta tras finalizar el análisis; no se conserva el binario, solo el registro de que la sesión usó una fuente tipo "upload" (ver Datos persistidos).

**RF-3. Fuente cámara**
- RF-3.1 El sistema debe solicitar permiso de acceso a la cámara vía navegador (getUserMedia/WebRTC).
- RF-3.2 El sistema debe enumerar las cámaras disponibles en el dispositivo (mediante `enumerateDevices`) y permitir al usuario seleccionar cuál utilizar a través de un selector de cámara. Si el usuario no selecciona ninguna, se utiliza la cámara por defecto del dispositivo. La selección puede cambiarse antes de iniciar el análisis; no es necesario cambiarla en caliente mientras el análisis está activo.
- RF-3.3 El análisis de cámara es siempre en tiempo real; no se soporta pausa (a diferencia del archivo cargado).
- RF-3.4 Si se pierde la conexión/el stream de cámara durante el análisis, el sistema debe mostrar únicamente un mensaje de error; no se implementa reintento automático.

**RF-4.** El sistema debe exponer una interfaz común (puerto) `VideoSource` que entregue frames/stream de forma homogénea al pipeline de análisis YOLO del backend, sin importar la fuente concreta seleccionada.

**RF-5.** El sistema debe permitir cambiar de fuente sin reiniciar la app, deteniendo y liberando correctamente los recursos de la fuente anterior antes de iniciar la nueva.

**RF-6.** El sistema debe mostrar errores claros cuando una fuente no pueda inicializarse (archivo corrupto o mayor a 256 MB; cámara no disponible/permiso denegado).

**RF-7.** El sistema debe registrar (log) inicio/fin/error de cada sesión de fuente de video para trazabilidad.

**RF-8.** El sistema debe registrar el **tipo de fuente** utilizada en cada sesión de análisis (`upload` | `live`), incluso cuando el archivo subido se descarta al finalizar.

### Arquitectura sugerida (evitando sobreingeniería)

- Un **puerto** `VideoSource` (interfaz) con métodos mínimos, por ejemplo `start()`, `stop()`, `onFrame(callback)`.
- Dos **adaptadores concretos**, cada uno implementando el puerto:
  - `FileVideoSource`: sube el archivo .mp4 (máx. 256 MB, con progreso) y lo entrega al backend para el análisis; se descarta tras finalizar.
  - `CameraVideoSource`: lista las cámaras disponibles del navegador (`enumerateDevices`), permite seleccionar una cámara específica (o la cámara por defecto), captura video de la cámara seleccionada (getUserMedia/WebRTC) y lo transmite en tiempo real al backend.
- Un `VideoSourceFactory` simple (Factory Method) que instancia el adaptador correcto según el tipo elegido — sin necesidad de un contenedor de inyección de dependencias complejo.
- El pipeline de inferencia YOLO (backend, ya implementado) permanece intacto; los adaptadores solo se encargan de la ingestión y entrega de frames/stream hacia ese pipeline existente.
- **Se evita deliberadamente**: soporte de fuentes adicionales (URL/streaming remoto), reintentos/reconexión automática, capas de abstracción no requeridas, event bus genérico, microservicios separados por fuente. Con dos implementaciones fijas y una sola fuente activa a la vez, una interfaz + factory es suficiente.

## Datos persistidos

- **Metadata de sesión de análisis**: tipo de fuente (`upload` | `live`), referencia cuando aplique (el nombre original del archivo antes de descartarlo), fecha/hora de inicio y fin, estado (activa/finalizada/error).
- Para fuente `upload`: **no se persiste el archivo .mp4**; solo queda el registro del tipo de fuente (y opcionalmente el nombre original) asociado a la sesión.
- Para fuente `live`: no se persiste el contenido del stream, solo la metadata de la sesión.

## Casos límite

- Archivo .mp4 corrupto o con códec no soportado.
- Archivo que excede los 256 MB (debe rechazarse antes o durante la subida, sin bloquear la UI).
- Usuario deniega el permiso de cámara.
- Dispositivo sin cámara disponible (el selector de cámara debe reflejar la lista vacía y el sistema debe mostrar un error claro).
- Cámara seleccionada desconectada u ocupada por otra aplicación durante el análisis → solo mensaje de error, sin reintento automático.
- Cámara desconectada en el momento de iniciar el análisis (no aparece en `enumerateDevices` o getUserMedia falla para el `deviceId` elegido) → error claro y análisis no iniciado.
- Cambio de fuente con un análisis en curso (liberación correcta de recursos, sin fugas ni handles colgados; solo una fuente activa a la vez).
- Resolución/FPS de la fuente incompatible con lo esperado por el modelo YOLO (requiere normalización previa, ya cubierta por el backend existente).

## Fuera de alcance

- Soporte de fuentes de video remotas (URL, RTSP, RTMP, HLS).
- Cualquier tipo de autenticación en las fuentes de video (archivo o cámara).
- Cambio de cámara en caliente mientras el análisis está activo (la selección de cámara se realiza antes de iniciar el análisis).
- Reintento/reconexión automática ante cortes de conexión de cámara; solo se notifica el error.
- Análisis simultáneo de más de una fuente de video en la misma sesión.
- Persistencia del archivo .mp4 subido más allá de la sesión de análisis (se descarta siempre al finalizar).
- Grabación/exportación del video con las detecciones superpuestas.
- Integración con almacenamiento en la nube (S3, GCS, etc.).
- Cambios al pipeline de inferencia YOLO en el backend (ya implementado y fuera de esta spec).
- Consideraciones específicas de soporte para dispositivos móviles (la app es solo web/escritorio).

## Criterios de finalización

- Las dos fuentes (archivo .mp4 hasta 256 MB, cámara) pueden seleccionarse, una a la vez, y entregan frames/stream correctamente al pipeline YOLO del backend.
- La subida de archivo muestra un indicador de progreso y rechaza archivos mayores a 256 MB.
- El sistema enumera las cámaras disponibles y permite al usuario seleccionar una cámara distinta a la por defecto antes de iniciar el análisis.
- Ante un corte de conexión en vivo de la cámara, el sistema muestra solo un mensaje de error, sin reintento automático.
- Cambiar de fuente libera correctamente los recursos de la anterior (sin fugas de memoria, streams colgados o cámara bloqueada).
- El archivo .mp4 subido se descarta tras el análisis y la sesión queda registrada con su tipo de fuente (`upload` | `live`).
- Existe una única interfaz `VideoSource` que el módulo de detección consume, y los dos adaptadores la implementan sin mezclar lógica de detección ni tocar el pipeline de inferencia existente.
- Verificación manual (sin suite automatizada, constitución principio 4) confirma: inicialización exitosa y fallida de cada fuente, enumeración y selección de cámaras, y el cambio de fuente en caliente.
- Documentación técnica de la interfaz `VideoSource` disponible para agregar futuras fuentes sin modificar el core.

## Dudas abiertas

Sin dudas abiertas pendientes.