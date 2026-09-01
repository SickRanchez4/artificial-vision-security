import { createRouter, createWebHistory } from 'vue-router'

import { useSession } from '../stores/session.js'
import ChatView from '../views/ChatView.vue'
import LoginView from '../views/LoginView.vue'
import ReportsView from '../views/ReportsView.vue'
import StreamView from '../views/StreamView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/transmision' },
    { path: '/login', name: 'login', component: LoginView },
    {
      path: '/transmision',
      name: 'stream',
      component: StreamView,
      meta: { requiresAuth: true },
    },
    {
      path: '/reportes',
      name: 'reports',
      component: ReportsView,
      meta: { requiresAuth: true },
    },
    {
      path: '/chatbot',
      name: 'chat',
      component: ChatView,
      meta: { requiresAuth: true },
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach((to) => {
  const { isAuthenticated } = useSession()
  if (to.meta.requiresAuth && !isAuthenticated.value) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && isAuthenticated.value) {
    return { name: 'stream' }
  }
})

export default router
