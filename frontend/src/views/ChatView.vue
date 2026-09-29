<script setup>
import { nextTick, onMounted, ref } from 'vue'

import { askChat, clearChatHistory, getChatHistory } from '../services/api.js'

const GREETING = { role: 'assistant', text: 'Puedo responder preguntas sobre los reportes de seguridad registrados.' }

// La conversación se conserva en localStorage para que el historial
// guardado en la base de datos siga siendo consultable tras recargar la
// página (POC mínimo, sin login por conversación).
let conversationId = localStorage.getItem('chat_conversation_id')
if (!conversationId) {
  conversationId = crypto.randomUUID()
  localStorage.setItem('chat_conversation_id', conversationId)
}

const messages = ref([GREETING])
const question = ref('')
const historyLoading = ref(true)
const loading = ref(false)
const clearing = ref(false)
const errorMessage = ref('')
const chatLog = ref(null)
let lastQuestion = ''

onMounted(async () => {
  try {
    const { messages: history } = await getChatHistory(conversationId)
    if (history.length) {
      messages.value = history.map((message) => ({ role: message.role, text: message.content }))
    }
  } catch {
    // Si falla la carga del historial, se sigue con el saludo por defecto.
  } finally {
    historyLoading.value = false
  }
})

async function sendQuestion(value = question.value) {
  const text = value.trim()
  if (!text || loading.value || clearing.value || historyLoading.value) return
  lastQuestion = text
  if (value === question.value) {
    messages.value.push({ role: 'user', text })
    question.value = ''
  }
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await askChat(text, conversationId)
    messages.value.push({ role: 'assistant', text: response.answer })
  } catch (error) {
    errorMessage.value = error.message
  } finally {
    loading.value = false
    await nextTick()
    chatLog.value?.scrollTo({ top: chatLog.value.scrollHeight, behavior: 'smooth' })
  }
}

async function clearChat() {
  if (clearing.value || loading.value || historyLoading.value) return
  clearing.value = true
  errorMessage.value = ''
  try {
    await clearChatHistory(conversationId)
    messages.value = [GREETING]
    question.value = ''
    lastQuestion = ''
  } catch (error) {
    errorMessage.value = error.message
  } finally {
    clearing.value = false
  }
}
</script>

<template>
  <section class="chat-page">
    <div class="page-heading">
      <div>
        <div class="eyebrow">Consultas sobre incidentes</div>
        <h1>Chatbot de reportes</h1>
      </div>
      <button type="button" class="danger-button" :disabled="clearing || loading || historyLoading" @click="clearChat">Limpiar chat</button>
    </div>
    <div class="chat-card">
      <div ref="chatLog" class="chat-log" aria-live="polite">
        <div v-for="(message, index) in messages" :key="index" class="message" :class="message.role">
          {{ message.text }}
        </div>
        <div v-if="loading" class="message assistant typing">Analizando reportes…</div>
      </div>
      <div v-if="errorMessage" class="chat-error">
        <span>{{ errorMessage }}</span>
        <button type="button" @click="sendQuestion(lastQuestion)">Reintentar</button>
      </div>
      <form class="chat-form" @submit.prevent="sendQuestion()">
        <label class="sr-only" for="question">Pregunta sobre los reportes</label>
        <input id="question" v-model="question" placeholder="Ej.: ¿Cuántas detecciones hubo hoy?" :disabled="loading || clearing || historyLoading" />
        <button class="primary-button" type="submit" :disabled="loading || clearing || historyLoading || !question.trim()">Enviar</button>
      </form>
    </div>
  </section>
</template>
