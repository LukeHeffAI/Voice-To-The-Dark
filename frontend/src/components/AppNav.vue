<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'
import { useNotificationStore } from '@/stores/notifications'

const auth = useAuthStore()
const router = useRouter()
const notify = useNotificationStore()

async function handleLogout() {
  await auth.logout()
  notify.show('Logged out', 'info')
  router.push('/login')
}
</script>

<template>
  <nav class="flex items-center justify-end gap-5 px-5 py-3 text-[0.8rem] relative z-10">
    <template v-if="auth.isLoggedIn">
      <span class="text-text-2 font-medium">{{ auth.user?.username }}</span>
      <router-link to="/settings" class="text-text-3 hover:text-text-2 transition-colors no-underline tracking-wide">
        Settings
      </router-link>
      <button
        @click="handleLogout"
        class="text-text-3 hover:text-text-2 transition-colors bg-transparent border-none cursor-pointer tracking-wide text-[0.8rem]"
      >
        Logout
      </button>
    </template>
    <template v-else>
      <router-link to="/login" class="text-text-3 hover:text-text-2 transition-colors no-underline tracking-wide">
        Login
      </router-link>
    </template>
  </nav>
</template>
