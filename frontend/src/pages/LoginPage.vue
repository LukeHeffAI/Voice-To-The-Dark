<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useNotificationStore } from '../stores/notifications'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const notifications = useNotificationStore()

const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function handleLogin() {
  error.value = ''
  if (!username.value || !password.value) {
    error.value = 'Please enter username and password'
    return
  }

  loading.value = true
  try {
    await auth.login(username.value, password.value)
    notifications.show('Signed in', 'success')
    const next = (route.query.next as string) || '/'
    // Only allow safe internal paths (must start with / and not contain //)
    const safePath = next.startsWith('/') && !next.startsWith('//') && !next.includes('://') ? next : '/'
    router.push(safePath)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Login failed'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-container">
    <h1 class="login-title">Voice In The Dark</h1>
    <p class="login-subtitle">Sign in to continue</p>

    <form class="login-form" @submit.prevent="handleLogin">
      <div class="form-group">
        <input
          v-model="username"
          type="text"
          placeholder="Username"
          autocomplete="username"
          class="form-input"
        />
      </div>
      <div class="form-group">
        <input
          v-model="password"
          type="password"
          placeholder="Password"
          autocomplete="current-password"
          class="form-input"
        />
      </div>

      <div v-if="error" class="form-error">{{ error }}</div>

      <button type="submit" class="login-btn" :disabled="loading">
        {{ loading ? 'Signing in...' : 'Sign in' }}
      </button>
    </form>
  </div>
</template>

<style scoped>
.login-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: calc(100vh - 200px);
  max-width: 380px;
  margin: 0 auto;
}

.login-title {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 2rem;
  font-weight: 400;
  color: rgba(255, 255, 255, 0.9);
  margin-bottom: 0.25rem;
  letter-spacing: 0.03em;
}

.login-subtitle {
  color: #555;
  font-size: 0.85rem;
  margin-bottom: 2rem;
}

.login-form {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.form-group {
  width: 100%;
}

.form-input {
  width: 100%;
  padding: 0.7rem 0.9rem;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 10px;
  color: #e8e6e3;
  font-size: 0.9rem;
  font-family: inherit;
  transition: border-color 0.2s;
}
.form-input::placeholder {
  color: #555;
}
.form-input:focus {
  outline: none;
  border-color: rgba(160, 32, 32, 0.5);
}

.form-error {
  color: #e07070;
  font-size: 0.8rem;
  text-align: center;
}

.login-btn {
  width: 100%;
  padding: 0.7rem;
  background: var(--color-accent);
  border: none;
  border-radius: 10px;
  color: white;
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
  margin-top: 0.25rem;
}
.login-btn:hover:not(:disabled) {
  background: var(--color-accent-hover);
}
.login-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
