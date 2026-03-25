<script setup lang="ts">
import { useNotificationStore } from '@/stores/notifications'

const notify = useNotificationStore()
</script>

<template>
  <div class="fixed bottom-6 left-1/2 -translate-x-1/2 z-[10001] flex flex-col items-center gap-2 pointer-events-none">
    <TransitionGroup name="toast">
      <div
        v-for="toast in notify.toasts"
        :key="toast.id"
        class="toast-item pointer-events-auto"
        :class="[`toast-${toast.type}`]"
        @click="notify.dismiss(toast.id)"
      >
        {{ toast.message }}
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-item {
  padding: 0.65rem 1.3rem;
  background: #1a1a1a;
  border: 1px solid var(--color-border-hover);
  border-radius: var(--radius-md);
  color: var(--color-text-1);
  font-size: 0.8rem;
  cursor: pointer;
  white-space: nowrap;
}
.toast-error { border-color: rgba(204,68,68,0.3); }
.toast-success { border-color: rgba(58,125,92,0.3); }
.toast-warn { border-color: rgba(184,160,64,0.3); }

.toast-enter-active { transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1); }
.toast-leave-active { transition: all 0.25s ease-in; }
.toast-enter-from { opacity: 0; transform: translateY(20px); }
.toast-leave-to { opacity: 0; transform: translateY(-10px); }
</style>
