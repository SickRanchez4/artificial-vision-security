<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

import { deleteEvents, getEvent, getEvents } from '../services/api.js'

const events = ref([])
const selectedEvent = ref(null)
const errorMessage = ref('')
const deleting = ref(false)
let refreshTimer
let requestGeneration = 0

function formatDate(value) {
  return new Intl.DateTimeFormat('es', { dateStyle: 'medium', timeStyle: 'medium' }).format(new Date(value))
}

async function loadEvents() {
  if (deleting.value) return
  const generation = requestGeneration
  try {
    const updatedEvents = await getEvents()
    if (generation !== requestGeneration) return
    events.value = updatedEvents
    errorMessage.value = ''
    if (selectedEvent.value) {
      const detail = await getEvent(selectedEvent.value.id)
      if (generation === requestGeneration) selectedEvent.value = detail
    }
  } catch (error) {
    if (generation === requestGeneration) errorMessage.value = error.message
  }
}

async function selectEvent(event) {
  if (deleting.value) return
  const generation = requestGeneration
  try {
    const detail = await getEvent(event.id)
    if (generation === requestGeneration) selectedEvent.value = detail
  } catch (error) {
    if (generation === requestGeneration) errorMessage.value = error.message
  }
}

async function deleteReports() {
  if (deleting.value || !events.value.length) return
  if (!window.confirm('¿Borrar todos los reportes y sus capturas? Esta acción no se puede deshacer.')) return

  deleting.value = true
  requestGeneration += 1
  errorMessage.value = ''
  try {
    await deleteEvents()
    events.value = []
    selectedEvent.value = null
  } catch (error) {
    errorMessage.value = error.message
  } finally {
    deleting.value = false
  }
}

onMounted(() => {
  loadEvents()
  refreshTimer = window.setInterval(loadEvents, 5000)
})
onBeforeUnmount(() => window.clearInterval(refreshTimer))
</script>

<template>
  <section>
    <div class="page-heading">
      <div>
        <div class="eyebrow">Historial de incidentes</div>
        <h1>Reportes de seguridad</h1>
      </div>
      <div class="heading-actions">
        <button class="ghost-button" type="button" :disabled="deleting" @click="loadEvents">Actualizar</button>
        <button class="danger-button" type="button" :disabled="deleting || !events.length" @click="deleteReports">Borrar reportes</button>
      </div>
    </div>

    <p v-if="errorMessage" class="error-message" role="alert">{{ errorMessage }}</p>
    <div v-if="events.length" class="reports-layout">
      <div class="report-list">
        <button
          v-for="event in events"
          :key="event.id"
          class="report-item"
          :class="{ selected: selectedEvent?.id === event.id }"
          type="button"
          :disabled="deleting"
          @click="selectEvent(event)"
        >
          <img :src="event.image_url" alt="Captura del evento" />
          <span>
            <strong>{{ event.weapon_class_label }}</strong>
            <small>{{ formatDate(event.detected_at) }}</small>
            <small>{{ Math.round(event.confidence * 100) }} % · {{ event.analysis_status_label }}</small>
          </span>
        </button>
      </div>

      <article v-if="selectedEvent" class="report-detail">
        <img :src="selectedEvent.image_url" alt="Captura íntegra del evento seleccionado" />
        <div class="report-detail-body">
          <div class="eyebrow">{{ selectedEvent.analysis_status_label }}</div>
          <h2>{{ selectedEvent.weapon_class_label }}</h2>
          <p class="muted">{{ formatDate(selectedEvent.detected_at) }} · Confianza {{ Math.round(selectedEvent.confidence * 100) }} %</p>
          <h3>Reporte del análisis</h3>
          <p>{{ selectedEvent.report_text || 'El análisis no produjo un reporte.' }}</p>
        </div>
      </article>
      <div v-else class="empty-state">Selecciona un reporte para ver todos sus detalles.</div>
    </div>
    <div v-else-if="!errorMessage" class="empty-state">
      <strong>Todavía no hay reportes</strong>
      <span>Las detecciones aparecerán aquí automáticamente.</span>
    </div>
  </section>
</template>
