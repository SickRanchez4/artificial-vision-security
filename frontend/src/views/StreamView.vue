<script setup>
import { ref } from 'vue'

const streamError = ref(false)
const streamUrl = '/api/stream'
</script>

<template>
  <section>
    <div class="page-heading">
      <div>
        <div class="eyebrow">Monitoreo activo</div>
        <h1>Transmisión de cámara</h1>
      </div>
      <span class="status-pill" :class="{ danger: streamError }">
        {{ streamError ? 'Cámara sin señal' : 'En directo' }}
      </span>
    </div>
    <div class="stream-frame">
      <img
        :src="streamUrl"
        alt="Transmisión de la cámara de seguridad"
        @load="streamError = false"
        @error="streamError = true"
      />
      <div class="stream-meta">Detección activa</div>
    </div>
  </section>
</template>
