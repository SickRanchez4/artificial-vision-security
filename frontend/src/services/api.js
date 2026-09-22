import { useSession } from '../stores/session.js'

const { setAuthenticated } = useSession()

export async function apiRequest(path, options = {}) {
  const response = await fetch(path, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  })

  if (response.status === 401 && path !== '/api/login') {
    setAuthenticated(false)
    window.location.assign('/login')
  }

  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(data.error || 'No se pudo completar la solicitud.')
  }
  return data
}

export function login(username, password) {
  return apiRequest('/api/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}

export function logout() {
  return apiRequest('/api/logout', { method: 'POST' })
}

export function getEvents() {
  return apiRequest('/api/events')
}

export function getEvent(eventId) {
  return apiRequest(`/api/events/${eventId}`)
}

export function askChat(question, conversationId) {
  return apiRequest('/api/chat', {
    method: 'POST',
    body: JSON.stringify({ question, conversation_id: conversationId }),
  })
}

/**
 * Sube un archivo .mp4 al backend para iniciar el análisis (RF-2).
 * Usa XMLHttpRequest (en vez de fetch) porque necesita el evento
 * `progress` para mostrar el avance de la subida (RF-2.3).
 */
export function uploadVideoFile(file, onProgress) {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest()
    request.open('POST', '/api/streaming/source')
    request.withCredentials = true

    request.upload.addEventListener('progress', (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100))
      }
    })

    request.addEventListener('load', () => {
      let data = {}
      try {
        data = JSON.parse(request.responseText || '{}')
      } catch {
        data = {}
      }
      if (request.status === 401) {
        setAuthenticated(false)
        window.location.assign('/login')
        return
      }
      if (request.status >= 200 && request.status < 300) {
        resolve(data)
      } else {
        reject(new Error(data.error || 'No se pudo subir el archivo.'))
      }
    })

    request.addEventListener('error', () => {
      reject(new Error('No se pudo subir el archivo.'))
    })

    const formData = new FormData()
    formData.append('file', file)
    request.send(formData)
  })
}

export function deleteVideoSource() {
  return apiRequest('/api/streaming/source', { method: 'DELETE' })
}

/** Crea una sesión de fuente "cámara" en el backend (RF-1, RF-3). */
export function createLiveSource() {
  return apiRequest('/api/streaming/source', {
    method: 'POST',
    body: JSON.stringify({ type: 'live' }),
  })
}

/** Consulta el estado de la fuente activa (RF-6). */
export function getSourceStatus() {
  return apiRequest('/api/streaming/source/status')
}

/**
 * Informa al backend de un error detectado en el navegador (cámara perdida,
 * permiso revocado en caliente) para que cierre la sesión con ese mensaje,
 * sin reintento automático (RF-3.4, RF-6).
 */
export function reportSourceError(message) {
  return apiRequest('/api/streaming/source/error', {
    method: 'POST',
    body: JSON.stringify({ message }),
  })
}
