<script setup>
import { useRouter } from 'vue-router'

import { logout } from './services/api.js'
import { useSession } from './stores/session.js'

const router = useRouter()
const { isAuthenticated, setAuthenticated } = useSession()

async function handleLogout() {
  try {
    await logout()
  } finally {
    setAuthenticated(false)
    await router.push('/login')
  }
}
</script>

<template>
  <div class="app-shell">
    <header v-if="isAuthenticated" class="topbar">
      <RouterLink class="brand" to="/transmision">
        <span class="brand-mark" aria-hidden="true">◉</span>
        <span>Seguridad escolar</span>
      </RouterLink>
      <nav aria-label="Navegación principal">
        <RouterLink to="/transmision">Transmisión</RouterLink>
        <RouterLink to="/reportes">Reportes</RouterLink>
        <RouterLink to="/chatbot">Chatbot</RouterLink>
      </nav>
      <button class="ghost-button" type="button" @click="handleLogout">Cerrar sesión</button>
    </header>
    <main :class="{ 'content-shell': isAuthenticated }">
      <RouterView />
    </main>
  </div>
</template>
