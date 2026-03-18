import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Toast, ToastType } from '@/types'

let nextId = 0

export const useNotificationStore = defineStore('notifications', () => {
  const toasts = ref<Toast[]>([])

  function show(message: string, type: ToastType = 'info', timeout = 3000) {
    const id = nextId++
    toasts.value.push({ id, message, type, timeout })
    if (timeout > 0) {
      setTimeout(() => dismiss(id), timeout)
    }
  }

  function dismiss(id: number) {
    toasts.value = toasts.value.filter((t) => t.id !== id)
  }

  return { toasts, show, dismiss }
})
