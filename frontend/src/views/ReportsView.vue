<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

import { getEvent, getEvents } from '../services/api.js'

const events = ref([])
const selectedEvent = ref(null)
const errorMessage = ref('')
let refreshTimer

function formatDate(value) {
  return new Intl.DateTimeFormat('es', { dateStyle: 'medium', timeStyle: 'medium' }).format(new Date(value))
}

async function loadEvents() {
  try {
    events.value = await getEvents()
    errorMessage.value = ''
    if (selectedEvent.value) {
      selectedEvent.value = await getEvent(selectedEvent.value.id)
    }
  } catch (error) {
    errorMessage.value = error.message
  }
}

async function selectEvent(event) {
  try {
    selectedEvent.value = await getEvent(event.id)
  } catch (error) {
    errorMessage.value = error.message
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
      <button class="ghost-button" type="button" @click="loadEvents">Actualizar</button>
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
