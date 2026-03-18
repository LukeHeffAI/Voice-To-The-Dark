<script setup lang="ts">
import { computed } from 'vue'
import type { TaskStatus } from '@/types'

const props = defineProps<{
  task: TaskStatus | null
}>()

const percent = computed(() => {
  if (!props.task || props.task.progress_total === 0) return 0
  return Math.round((props.task.progress_current / props.task.progress_total) * 100)
})

const isIndeterminate = computed(() => {
  if (!props.task) return true
  return (
    props.task.progress_total === 0 ||
    props.task.status === 'queued' ||
    props.task.status === 'processing' ||
    props.task.status === 'mixing'
  )
})
</script>

<template>
  <div v-if="task" class="task-progress">
    <div class="progress-message">{{ task.progress_message }}</div>
    <div class="progress-bar-track">
      <div
        class="progress-bar-fill"
        :class="{ indeterminate: isIndeterminate }"
        :style="isIndeterminate ? {} : { width: percent + '%' }"
      />
    </div>
    <div v-if="!isIndeterminate" class="progress-percent">{{ percent }}%</div>
  </div>
</template>

<style scoped>
.task-progress {
  margin-top: 0.5rem;
}
.progress-message {
  font-size: 0.78rem;
  color: var(--color-text-3);
  margin-bottom: 0.4rem;
}
.progress-bar-track {
  width: 100%;
  height: 4px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 2px;
  overflow: hidden;
}
.progress-bar-fill {
  height: 100%;
  background: var(--color-accent);
  border-radius: 2px;
  transition: width 0.3s ease;
}
.progress-bar-fill.indeterminate {
  width: 0%;
  animation: indeterminate 1.8s cubic-bezier(0.65, 0, 0.35, 1) infinite;
}
.progress-percent {
  font-size: 0.72rem;
  color: var(--color-text-3);
  margin-top: 0.25rem;
  text-align: right;
}
@keyframes indeterminate {
  0% {
    width: 0%;
    margin-left: 0;
  }
  50% {
    width: 35%;
    margin-left: 35%;
  }
  100% {
    width: 0%;
    margin-left: 100%;
  }
}
</style>
