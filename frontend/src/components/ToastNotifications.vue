<script setup lang="ts">
import { useNotificationStore } from '../stores/notifications'

const notifications = useNotificationStore()
</script>

<template>
  <TransitionGroup name="toast" tag="div" class="toast-container">
    <div
      v-for="msg in notifications.messages"
      :key="msg.id"
      class="toast-item"
      :class="msg.type"
      @click="notifications.dismiss(msg.id)"
    >
      {{ msg.text }}
    </div>
  </TransitionGroup>
</template>

<style scoped>
.toast-container {
  position: fixed;
  bottom: 1.5rem;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10001;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  pointer-events: none;
}

.has-miniplayer .toast-container {
  bottom: 4.5rem;
}

.toast-item {
  padding: 0.65rem 1.3rem;
  background: #1a1a1a;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 10px;
  color: #e8e6e3;
  font-size: 0.8rem;
  pointer-events: auto;
  cursor: pointer;
  white-space: nowrap;
}

.toast-item.success {
  border-color: rgba(58, 125, 92, 0.4);
}
.toast-item.error {
  border-color: rgba(204, 68, 68, 0.4);
}

.toast-enter-active {
  transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}
.toast-leave-active {
  transition: all 0.25s ease-in;
}
.toast-enter-from {
  opacity: 0;
  transform: translateY(20px);
}
.toast-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
