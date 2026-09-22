<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { createLiveSource, deleteVideoSource, reportSourceError, uploadVideoFile } from '../services/api.js'
import { CameraCapture, listCameras } from '../services/videoCapture.js'

const streamError = ref(false)
const streamUrl = '/api/stream'

// RF-1: solo una fuente puede estar activa a la vez.
const sourceType = ref('file')

const selectedFile = ref(null)
const uploadProgress = ref(0)
const isUploading = ref(false)
const uploadError = ref('')

const cameras = ref([])
const selectedCameraId = ref('')
const isCameraActive = ref(false)
const cameraError = ref('')
let cameraCapture = null

function onFileSelected(event) {
  const file = event.target.files?.[0]
  uploadError.value = ''
  selectedFile.value = file || null
}

async function startFileAnalysis() {
  if (!selectedFile.value || isUploading.value) return
  isUploading.value = true
  uploadProgress.value = 0
  uploadError.value = ''
  try {
    await uploadVideoFile(selectedFile.value, (percent) => {
      uploadProgress.value = percent
    })
  } catch (error) {
    uploadError.value = error.message
  } finally {
    isUploading.value = false
  }
}

async function stopAnalysis() {
  stopCamera()
  try {
    await deleteVideoSource()
  } catch {
    // Sin reintento automático (constitución/spec): el usuario puede
    // intentar de nuevo manualmente si falla.
  }
}

// RF-3.2: enumerar cámaras requiere permiso previo para obtener etiquetas;
// se solicita un permiso "de descubrimiento" que se libera enseguida.
async function refreshCameraList() {
  cameraError.value = ''
  try {
    const probe = await navigator.mediaDevices.getUserMedia({ video: true })
    probe.getTracks().forEach((track) => track.stop())
    cameras.value = await listCameras()
  } catch {
    cameras.value = []
    cameraError.value = 'No se pudo acceder a la cámara. Verifica los permisos del navegador.'
  }
}

async function startCamera() {
  if (isCameraActive.value) return
  cameraError.value = ''
  try {
    cameraCapture = new CameraCapture()
    await cameraCapture.start(selectedCameraId.value || undefined)
    await createLiveSource()
    cameraCapture.beginStreaming((error) => {
      cameraError.value = error.message
      isCameraActive.value = false
      // RF-3.4: un único aviso de error, sin reintento automático.
      reportSourceError(error.message).catch(() => {})
    })
    isCameraActive.value = true
  } catch (error) {
    cameraError.value = error.message || 'No se pudo iniciar la cámara.'
    stopCamera()
  }
}

function stopCamera() {
  if (cameraCapture) {
    cameraCapture.stop()
    cameraCapture = null
  }
  isCameraActive.value = false
}

watch(sourceType, (newType, oldType) => {
  if (oldType === 'camera' && newType !== 'camera') {
    stopCamera()
  }
  if (newType === 'camera') {
    refreshCameraList()
  }
})

onBeforeUnmount(() => {
  stopCamera()
})
</script>

<template>
  <section>
    <div class="page-heading">
      <div>
        <div class="eyebrow">Monitoreo activo</div>
        <h1>Transmisión de cámara</h1>
      </div>
      <span class="status-pill" :class="{ danger: streamError }">
        {{ streamError ? 'Sin fuente activa' : 'En directo' }}
      </span>
    </div>

    <div class="source-tabs">
      <button
        type="button"
        class="source-tab"
        :class="{ active: sourceType === 'file' }"
        @click="sourceType = 'file'"
      >
        Subir video
      </button>
      <button
        type="button"
        class="source-tab"
        :class="{ active: sourceType === 'camera' }"
        @click="sourceType = 'camera'"
      >
        Cámara
      </button>
    </div>

    <div v-if="sourceType === 'file'" class="upload-panel">
      <input type="file" accept="video/mp4" @change="onFileSelected" />
      <p v-if="selectedFile" class="selected-file-title">{{ selectedFile.name }}</p>
      <div class="upload-actions">
        <button type="button" class="primary-button" :disabled="!selectedFile || isUploading" @click="startFileAnalysis">
          {{ isUploading ? 'Subiendo…' : 'Iniciar análisis' }}
        </button>
        <button type="button" class="ghost-button" @click="stopAnalysis">Detener</button>
      </div>
      <div v-if="isUploading" class="upload-progress">
        <div class="upload-progress-bar" :style="{ width: uploadProgress + '%' }"></div>
        <span>{{ uploadProgress }}%</span>
      </div>
      <p v-if="uploadError" class="upload-error">{{ uploadError }}</p>
    </div>

    <div v-else class="upload-panel">
      <label for="camera-select">Cámara</label>
      <select id="camera-select" v-model="selectedCameraId" :disabled="isCameraActive">
        <option value="">Cámara por defecto</option>
        <option v-for="camera in cameras" :key="camera.deviceId" :value="camera.deviceId">
          {{ camera.label || `Cámara ${camera.deviceId.slice(0, 6)}` }}
        </option>
      </select>
      <p v-if="cameras.length === 0 && !cameraError" class="muted">
        No se detectaron cámaras disponibles.
      </p>

      <div class="upload-actions">
        <button type="button" class="primary-button" :disabled="isCameraActive" @click="startCamera">
          Iniciar análisis
        </button>
        <button type="button" class="ghost-button" @click="stopAnalysis">Detener</button>
      </div>
      <p v-if="cameraError" class="upload-error">{{ cameraError }}</p>
    </div>

    <div class="stream-frame">
      <img
        :src="streamUrl"
        alt="Análisis de la fuente de video activa"
        @load="streamError = false"
        @error="streamError = true"
      />
      <div class="stream-meta">Detección activa</div>
    </div>
  </section>
</template>



