<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import type { TaskStatus } from '../api/types'
import * as audioApi from '../api/audio'

const props = defineProps<{ taskId: number }>()
const emit = defineEmits<{
  completed: [result: Record<string, unknown> | null]
  failed: [error: string]
}>()

const task = ref<TaskStatus | null>(null)
const error = ref('')
let polling = false
let pollTimeout: ReturnType<typeof setTimeout> | null = null

async function poll() {
  if (!polling) return

  const currentTaskId = props.taskId
  try {
    const nextTask = await audioApi.getTaskStatus(currentTaskId)

    // Guard against stale responses after task ID changed
    if (!polling || currentTaskId !== props.taskId) return

    task.value = nextTask
    error.value = ''

    if (task.value.status === 'completed') {
      stopPolling()
      emit('completed', task.value.result)
    } else if (task.value.status === 'failed') {
      stopPolling()
      emit('failed', task.value.error_message)
    } else {
      scheduleNext()
    }
  } catch {
    if (!polling || currentTaskId !== props.taskId) return
    error.value = 'Failed to check task status'
    if (polling) scheduleNext()
  }
}

function scheduleNext() {
  if (polling) {
    pollTimeout = setTimeout(poll, 2000)
  }
}

function startPolling() {
  stopPolling()
  polling = true
  poll()
}

function stopPolling() {
  polling = false
  if (pollTimeout) {
    clearTimeout(pollTimeout)
    pollTimeout = null
  }
}

watch(() => props.taskId, () => {
  startPolling()
})

onMounted(startPolling)
onUnmounted(stopPolling)
</script>

<template>
  <div class="task-progress">
    <!-- Progress bar -->
    <div class="progress-track">
      <div
        class="progress-fill"
        :class="{ failed: task?.status === 'failed' }"
        :style="{ width: `${task?.progress ?? 0}%` }"
      />
    </div>

    <!-- Status line -->
    <div class="status-line">
      <span v-if="task?.status === 'queued'" class="status-dot queued" />
      <span v-else-if="task?.status === 'running'" class="status-dot running" />
      <span v-else-if="task?.status === 'completed'" class="status-check">✓</span>
      <span v-else-if="task?.status === 'failed'" class="status-x">✕</span>

      <span class="stage-text">
        {{ task?.stage || 'Starting...' }}
      </span>

      <span class="progress-pct">{{ task?.progress ?? 0 }}%</span>
    </div>

    <!-- Error message -->
    <div v-if="task?.status === 'failed'" class="error-msg">
      {{ task.error_message || 'An unknown error occurred' }}
    </div>

    <div v-if="error" class="error-msg">{{ error }}</div>
  </div>
</template>

<style scoped>
.task-progress {
  margin: 0.75rem 0;
}

.progress-track {
  height: 4px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 0.5rem;
}

.progress-fill {
  height: 100%;
  background: var(--color-accent);
  border-radius: 2px;
  transition: width 0.4s ease;
}

.progress-fill.failed {
  background: #b83030;
}

.status-line {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.78rem;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-dot.queued {
  background: #555;
}

.status-dot.running {
  background: var(--color-accent);
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.status-check {
  color: var(--color-success);
  font-size: 0.75rem;
  font-weight: 700;
}

.status-x {
  color: #b83030;
  font-size: 0.75rem;
  font-weight: 700;
}

.stage-text {
  color: #8a8a8a;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.progress-pct {
  color: #555;
  font-size: 0.72rem;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}

.error-msg {
  margin-top: 0.4rem;
  font-size: 0.75rem;
  color: #b83030;
  padding: 0.4rem 0.6rem;
  background: rgba(184, 48, 48, 0.08);
  border-radius: 6px;
  border: 1px solid rgba(184, 48, 48, 0.15);
}
</style>
