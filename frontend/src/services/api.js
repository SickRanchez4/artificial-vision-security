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
