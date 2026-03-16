<script setup lang="ts">
import { computed } from 'vue'
import type { Story } from '../api/types'

const props = defineProps<{ story: Story; hasScript: boolean }>()

const steps = computed(() => [
  {
    label: 'Story Fetched',
    done: true,
    active: !props.story.audio_file_path && !props.hasScript,
  },
  {
    label: 'Script Generated',
    done: props.hasScript,
    active: props.hasScript && !props.story.audio_file_path,
  },
  {
    label: 'Audio Ready',
    done: !!props.story.audio_file_path,
    active: false,
  },
])
</script>

<template>
  <div class="pipeline">
    <div
      v-for="(step, i) in steps"
      :key="i"
      class="step"
      :class="{ done: step.done, active: step.active }"
    >
      <div class="step-number">
        <span v-if="step.done" class="check">&#10003;</span>
        <span v-else>{{ i + 1 }}</span>
      </div>
      <span class="step-label">{{ step.label }}</span>
    </div>
  </div>
</template>

<style scoped>
.pipeline {
  display: flex;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}

.step {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.65rem 0.75rem;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 10px;
  font-size: 0.78rem;
  color: #555;
  transition: all 0.2s;
}

.step.done {
  border-color: rgba(58, 125, 92, 0.25);
  background: rgba(58, 125, 92, 0.06);
  color: var(--color-success);
}

.step.active {
  border-color: rgba(160, 32, 32, 0.25);
  background: rgba(160, 32, 32, 0.06);
  color: var(--color-accent);
}

.step-number {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.7rem;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.04);
  flex-shrink: 0;
}
.step.done .step-number {
  background: rgba(58, 125, 92, 0.15);
}
.step.active .step-number {
  background: rgba(160, 32, 32, 0.15);
}

.check {
  font-size: 0.65rem;
}

.step-label {
  font-weight: 500;
}
</style>
