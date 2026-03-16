import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi, ApiError } from '@/api/client'
import type { User } from '@/types'

export const useAuthStore = defineStore(
  'auth',
  () => {
    const token = ref<string | null>(null)
    const user = ref<User | null>(null)

    const isLoggedIn = computed(() => !!token.value)
    const isAdmin = computed(() => user.value?.is_admin ?? false)

    async function login(username: string, password: string) {
      const res = await authApi.login(username, password)
      token.value = res.access_token
      user.value = res.user
    }

    async function logout() {
      try {
        await authApi.logout()
      } catch {
        /* ignore */
      }
      token.value = null
      user.value = null
    }

    async function fetchMe() {
      if (!token.value) return
      try {
        user.value = await authApi.me()
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) {
          token.value = null
          user.value = null
        }
      }
    }

    return { token, user, isLoggedIn, isAdmin, login, logout, fetchMe }
  },
  {
    persist: {
      pick: ['token'],
    },
  },
)
