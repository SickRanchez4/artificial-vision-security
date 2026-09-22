/**
 * Captura de video desde la cámara del dispositivo (RF-3).
 *
 * Usa exclusivamente APIs nativas del navegador (MediaDevices, canvas): no
 * hace ninguna llamada al motor de detección ni al proveedor de reportes
 * (constitución, principio 3). Los frames capturados se envían al backend
 * por HTTP; el análisis ocurre siempre en el servidor.
 */

const CAPTURE_FPS = 3
const JPEG_QUALITY = 0.8

/**
 * Enumera las cámaras disponibles del dispositivo (RF-3.2).
 * Requiere haber pedido permiso de cámara al menos una vez para que el
 * navegador entregue las etiquetas (`label`) de cada dispositivo.
 */
export async function listCameras() {
  const devices = await navigator.mediaDevices.enumerateDevices()
  return devices.filter((device) => device.kind === 'videoinput')
}

/**
 * Controlador de una sesión de captura de cámara: pide permiso, abre el
 * stream con el `deviceId` elegido (o el de cámara por defecto si no se
 * especifica) y envía frames periódicos al backend mientras esté activa.
 */
export class CameraCapture {
  constructor() {
    this._stream = null
    this._video = null
    this._canvas = null
    this._intervalId = null
  }

  /**
   * Solicita permiso y abre la cámara seleccionada (RF-3.1). Lanza si el
   * usuario deniega el permiso o la cámara no está disponible.
   */
  async start(deviceId) {
    const constraints = { video: deviceId ? { deviceId: { exact: deviceId } } : true, audio: false }
    this._stream = await navigator.mediaDevices.getUserMedia(constraints)

    this._video = document.createElement('video')
    this._video.srcObject = this._stream
    this._video.muted = true
    await this._video.play()

    this._canvas = document.createElement('canvas')
  }

  /** Comienza a capturar y enviar frames al backend (RF-3.1, RF-3.3). */
  beginStreaming(onError) {
    // RF-3.4: si el sistema operativo/otra app desconecta la cámara en uso,
    // el track dispara "ended"; se notifica un único error, sin reintento.
    this._stream?.getVideoTracks().forEach((track) => {
      track.addEventListener('ended', () => {
        this.stop()
        if (onError) onError(new Error('Se perdió la conexión con la cámara.'))
      })
    })

    const intervalMs = Math.round(1000 / CAPTURE_FPS)
    this._intervalId = window.setInterval(() => {
      this._captureAndSendFrame().catch((error) => {
        if (onError) onError(error)
      })
    }, intervalMs)
  }

  async _captureAndSendFrame() {
    if (!this._video || !this._canvas) return
    const { videoWidth, videoHeight } = this._video
    if (!videoWidth || !videoHeight) return

    this._canvas.width = videoWidth
    this._canvas.height = videoHeight
    const context = this._canvas.getContext('2d')
    context.drawImage(this._video, 0, 0, videoWidth, videoHeight)

    const blob = await new Promise((resolve) => this._canvas.toBlob(resolve, 'image/jpeg', JPEG_QUALITY))
    if (!blob) return

    const response = await fetch('/api/streaming/camera-frame', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'image/jpeg' },
      body: blob,
    })

    // RF-3.4: sin reintento automático; se notifica el error y se detiene.
    if (!response.ok) {
      this.stop()
      throw new Error('Se perdió la conexión con la cámara.')
    }
  }

  /** Detiene el envío de frames y libera la cámara (RF-5). */
  stop() {
    if (this._intervalId !== null) {
      window.clearInterval(this._intervalId)
      this._intervalId = null
    }
    if (this._stream) {
      this._stream.getTracks().forEach((track) => track.stop())
      this._stream = null
    }
    this._video = null
    this._canvas = null
  }
}
