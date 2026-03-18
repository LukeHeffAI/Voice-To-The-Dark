<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useNotificationStore } from '@/stores/notifications'
import { ApiError } from '@/api/client'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const notify = useNotificationStore()

const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function handleLogin() {
  error.value = ''
  if (!username.value || !password.value) {
    error.value = 'Please enter username and password'
    return
  }
  loading.value = true
  try {
    await auth.login(username.value, password.value)
    notify.show('Welcome back', 'success')
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    const safeRedirect = redirect.startsWith('/') && !redirect.startsWith('//') ? redirect : '/'
    router.push(safeRedirect)
  } catch (e) {
    if (e instanceof ApiError) {
      const body = e.body as { detail?: string }
      error.value = body?.detail || 'Invalid credentials'
    } else {
      error.value = 'Login failed'
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="flex flex-col items-center justify-center min-h-[80vh] px-4 relative z-10">
    <div class="w-full max-w-[380px]">
      <h1 class="font-serif text-3xl text-text-1 text-center mb-2 tracking-wide">Voice In The Dark</h1>
      <p class="text-text-3 text-center text-sm mb-8">Sign in to continue</p>

      <form @submit.prevent="handleLogin" class="flex flex-col gap-4">
        <input
          v-model="username"
          type="text"
          placeholder="Username"
          autocomplete="username"
          class="form-input"
          @keydown.enter="handleLogin"
        />
        <input
          v-model="password"
          type="password"
          placeholder="Password"
          autocomplete="current-password"
          class="form-input"
          @keydown.enter="handleLogin"
        />

        <div
          v-if="error"
          class="py-2.5 px-3.5 rounded-[var(--radius-sm)] text-[0.82rem] bg-error-dim border border-error/20 text-[#e07070]"
        >
          {{ error }}
        </div>

        <button type="submit" class="btn-primary w-full mt-1" :disabled="loading">
          <span v-if="loading" class="spinner"></span>
          {{ loading ? 'Signing in...' : 'Sign In' }}
        </button>
      </form>

      <div class="text-center mt-6">
        <router-link to="/" class="text-text-3 hover:text-text-2 text-[0.8rem] no-underline transition-colors">
          &larr; Back to stories
        </router-link>
      </div>
    </div>
  </div>
</template>
