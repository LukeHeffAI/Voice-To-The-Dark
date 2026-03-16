import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as authApi from '../api/auth'
import type { User } from '../api/types'

export const useAuthStore = defineStore(
  'auth',
  () => {
    const user = ref<User | null>(null)
    const token = ref<string | null>(null)

    const isAuthenticated = computed(() => !!user.value)
    const isAdmin = computed(() => !!user.value?.is_admin)

    async function login(username: string, password: string) {
      const res = await authApi.login(username, password)
      user.value = res.user
      token.value = res.access_token
      localStorage.setItem('vttd_auth_token', res.access_token)
    }

    async function logout() {
      try {
        await authApi.logout()
      } catch {
        // Cookie deletion happens server-side; clear local state regardless
      }
      user.value = null
      token.value = null
      localStorage.removeItem('vttd_auth_token')
    }

    async function fetchMe() {
      try {
        user.value = await authApi.getMe()
      } catch {
        user.value = null
        token.value = null
        localStorage.removeItem('vttd_auth_token')
      }
    }

    /** Called once on app start to restore session from cookie. */
    async function init() {
      const savedToken = localStorage.getItem('vttd_auth_token')
      if (savedToken) {
        token.value = savedToken
      }
      // Try to fetch user profile — will work if cookie is valid
      await fetchMe()
    }

    return { user, token, isAuthenticated, isAdmin, login, logout, fetchMe, init }
  },
  {
    persist: {
      pick: ['user', 'token'],
    },
  },
)
