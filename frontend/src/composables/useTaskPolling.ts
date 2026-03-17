import { ref, onUnmounted } from 'vue'
import { tasksApi } from '@/api/client'
import type { TaskStatus } from '@/types'

/**
 * Composable for polling a background task's status.
 * Starts at 1s intervals, slowing to 2s after 10 polls, then 3s after 30.
 * Automatically stops on component unmount or when the task completes/fails.
 */
export function useTaskPolling() {
  const task = ref<TaskStatus | null>(null)
  const isPolling = ref(false)
  let timer: ReturnType<typeof setTimeout> | null = null
  let pollCount = 0

  function pollInterval(): number {
    if (pollCount < 10) return 1000
    if (pollCount < 30) return 2000
    return 3000
  }

  async function startPolling(
    taskId: number,
    onComplete?: (t: TaskStatus) => void,
  ) {
    stopPolling()
    isPolling.value = true
    pollCount = 0

    async function poll() {
      try {
        task.value = await tasksApi.getStatus(taskId)
        pollCount++

        if (task.value.status === 'complete' || task.value.status === 'failed') {
          isPolling.value = false
          onComplete?.(task.value)
          return
        }

        timer = setTimeout(poll, pollInterval())
      } catch {
        isPolling.value = false
      }
    }

    await poll()
  }

  function stopPolling() {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
    isPolling.value = false
  }

  onUnmounted(stopPolling)

  return { task, isPolling, startPolling, stopPolling }
}
