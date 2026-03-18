import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('../pages/LoginPage.vue'),
      meta: { guest: true },
    },
    {
      path: '/',
      name: 'home',
      component: () => import('../pages/HomePage.vue'),
    },
    {
      path: '/story/:id',
      name: 'story-detail',
      component: () => import('../pages/StoryDetailPage.vue'),
    },
    {
      path: '/story/:id/player',
      name: 'player',
      component: () => import('../pages/PlayerPage.vue'),
    },
    {
      path: '/story/:id/reader',
      name: 'reader',
      component: () => import('../pages/ReaderPage.vue'),
    },
    {
      path: '/story/:id/script',
      name: 'script-editor',
      component: () => import('../pages/ScriptEditorPage.vue'),
    },
    {
      path: '/submit',
      name: 'submit',
      component: () => import('../pages/SubmitPage.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/folder/:id',
      name: 'folder',
      component: () => import('../pages/FolderPage.vue'),
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('../pages/SettingsPage.vue'),
      meta: { requiresAuth: true },
    },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'login', query: { next: to.fullPath } }
  }
  if (to.meta.guest && auth.isAuthenticated) {
    return { name: 'home' }
  }
})

export default router
