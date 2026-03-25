import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/pages/HomePage.vue'),
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/pages/LoginPage.vue'),
    },
    {
      path: '/submit',
      name: 'submit',
      component: () => import('@/pages/SubmitPage.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/story/:id',
      name: 'story-detail',
      component: () => import('@/pages/StoryDetailPage.vue'),
    },
    {
      path: '/story/:id/edit',
      name: 'script-editor',
      component: () => import('@/pages/ScriptEditorPage.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/story/:id/play',
      name: 'player',
      component: () => import('@/pages/PlayerPage.vue'),
    },
    {
      path: '/story/:id/read',
      name: 'reader',
      component: () => import('@/pages/ReaderPage.vue'),
    },
    {
      path: '/folder/:id',
      name: 'folder',
      component: () => import('@/pages/FolderPage.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/pages/SettingsPage.vue'),
      meta: { requiresAuth: true },
    },
  ],
  scrollBehavior() {
    return { top: 0 }
  },
})

router.beforeEach((to) => {
  if (to.meta.requiresAuth) {
    const auth = useAuthStore()
    if (!auth.isLoggedIn) {
      return { name: 'login', query: { redirect: to.fullPath } }
    }
  }
})

export default router
