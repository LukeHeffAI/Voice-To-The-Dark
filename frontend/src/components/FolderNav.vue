<script setup lang="ts">
import type { Folder } from '../api/types'

defineProps<{
  folders: Folder[]
  activeId: number | null
}>()

const emit = defineEmits<{ select: [id: number | null] }>()
</script>

<template>
  <div class="folder-nav">
    <button
      class="folder-pill"
      :class="{ active: activeId === null }"
      @click="emit('select', null)"
    >
      Recent
    </button>
    <button
      v-for="folder in folders"
      :key="folder.id"
      class="folder-pill"
      :class="{ active: activeId === folder.id }"
      @click="emit('select', folder.id)"
    >
      {{ folder.name }}
      <span class="folder-count">{{ folder.story_count }}</span>
    </button>
  </div>
</template>

<style scoped>
.folder-nav {
  display: flex;
  gap: 0.5rem;
  overflow-x: auto;
  padding-bottom: 0.25rem;
  scrollbar-width: none;
}
.folder-nav::-webkit-scrollbar {
  display: none;
}

.folder-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.4rem 0.85rem;
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(255, 255, 255, 0.025);
  color: #8a8a8a;
  font-size: 0.78rem;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s;
  flex-shrink: 0;
}
.folder-pill:hover {
  background: rgba(255, 255, 255, 0.045);
  color: #e8e6e3;
}
.folder-pill.active {
  background: rgba(160, 32, 32, 0.12);
  border-color: rgba(160, 32, 32, 0.25);
  color: var(--color-accent);
}

.folder-count {
  font-size: 0.65rem;
  opacity: 0.6;
}
</style>
