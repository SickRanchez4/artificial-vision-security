<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { login } from '../services/api.js'
import { useSession } from '../stores/session.js'

const username = ref('')
const password = ref('')
const errorMessage = ref('')
const loading = ref(false)
const route = useRoute()
const router = useRouter()
const { setAuthenticated } = useSession()

async function submitLogin() {
  errorMessage.value = ''
  loading.value = true
  try {
    await login(username.value, password.value)
    setAuthenticated(true)
    const destination = typeof route.query.redirect === 'string'
      ? route.query.redirect
      : '/transmision'
    await router.push(destination)
  } catch (error) {
    errorMessage.value = error.message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section class="login-page">
    <div class="login-panel">
      <div class="eyebrow">Control de acceso</div>
      <h1>Centro de seguridad escolar</h1>
      <p class="intro">Ingresa con las credenciales autorizadas para acceder al monitoreo.</p>

      <form @submit.prevent="submitLogin">
        <label for="username">Usuario</label>
        <input
          id="username"
          v-model="username"
          name="username"
          autocomplete="username"
          required
        />

        <label for="password">Contraseña</label>
        <input
          id="password"
          v-model="password"
          name="password"
          type="password"
          autocomplete="current-password"
          required
        />

        <p v-if="errorMessage" class="error-message" role="alert">{{ errorMessage }}</p>
        <button class="primary-button" type="submit" :disabled="loading">
          {{ loading ? 'Verificando…' : 'Iniciar sesión' }}
        </button>
      </form>
    </div>
    <aside class="login-visual" aria-hidden="true">
      <div class="radar"><span></span></div>
      <p>Monitoreo inteligente<br />para entornos protegidos</p>
    </aside>
  </section>
</template>
