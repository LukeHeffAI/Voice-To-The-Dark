import { defineStore } from 'pinia'
import { ref } from 'vue'

export type NotificationType = 'success' | 'error' | 'info'

export interface Notification {
  id: number
  text: string
  type: NotificationType
}

let nextId = 0

export const useNotificationStore = defineStore('notifications', () => {
  const messages = ref<Notification[]>([])

  function show(text: string, type: NotificationType = 'info', timeout = 4000) {
    const id = ++nextId
    messages.value.push({ id, text, type })
    if (timeout > 0) {
      setTimeout(() => dismiss(id), timeout)
    }
  }

  function dismiss(id: number) {
    messages.value = messages.value.filter((m) => m.id !== id)
  }

  return { messages, show, dismiss }
})
