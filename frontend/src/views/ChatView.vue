<script setup>
import { nextTick, ref } from 'vue'

import { askChat } from '../services/api.js'

const conversationId = crypto.randomUUID()
const messages = ref([
  { role: 'assistant', text: 'Puedo responder preguntas sobre los reportes de seguridad registrados.' },
])
const question = ref('')
const loading = ref(false)
const errorMessage = ref('')
const chatLog = ref(null)
let lastQuestion = ''

async function sendQuestion(value = question.value) {
  const text = value.trim()
  if (!text || loading.value) return
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
</script>

<template>
  <section class="chat-page">
    <div class="page-heading">
      <div>
        <div class="eyebrow">Consultas sobre incidentes</div>
        <h1>Chatbot de reportes</h1>
      </div>
      <span class="status-pill">Sesión efímera</span>
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
        <input id="question" v-model="question" placeholder="Ej.: ¿Cuántas detecciones hubo hoy?" :disabled="loading" />
        <button class="primary-button" type="submit" :disabled="loading || !question.trim()">Enviar</button>
      </form>
    </div>
  </section>
</template>
