import { computed, ref } from 'vue'

const authenticated = ref(sessionStorage.getItem('authenticated') === 'true')

export function useSession() {
  const setAuthenticated = (value) => {
    authenticated.value = value
    if (value) {
      sessionStorage.setItem('authenticated', 'true')
    } else {
      sessionStorage.removeItem('authenticated')
    }
  }

  return {
    isAuthenticated: computed(() => authenticated.value),
    setAuthenticated,
  }
}
