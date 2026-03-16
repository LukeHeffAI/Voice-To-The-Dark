<script setup lang="ts">
import type { Folder } from '@/types'

defineProps<{
  folders: Folder[]
  activeFolderId?: number | null
}>()
</script>

<template>
  <nav class="folder-nav">
    <router-link
      to="/"
      class="folder-pill"
      :class="{ active: !activeFolderId }"
    >
      <span class="folder-pill-icon">&#9716;</span>
      <span>Recent</span>
    </router-link>
    <router-link
      v-for="f in folders"
      :key="f.id"
      :to="`/folder/${f.id}`"
      class="folder-pill"
      :class="{ active: activeFolderId === f.id }"
    >
      <span class="folder-pill-icon">&#9776;</span>
      <span>{{ f.name }}</span>
    </router-link>
  </nav>
</template>

<style scoped>
.folder-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
  margin-bottom: 1.5rem;
}
.folder-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.8rem;
  border: 1px solid var(--color-border);
  border-radius: 20px;
  color: var(--color-text-3);
  text-decoration: none;
  font-size: 0.75rem;
  font-weight: 500;
  letter-spacing: 0.02em;
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  background: transparent;
  max-width: 200px;
  overflow: hidden;
}
.folder-pill span:not(.folder-pill-icon) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.folder-pill:hover {
  border-color: var(--color-border-hover);
  color: var(--color-text-2);
  background: var(--color-surface);
}
.folder-pill.active {
  border-color: var(--color-accent);
  color: var(--color-accent);
  background: var(--color-accent-dim);
}
.folder-pill-icon { font-size: 0.8rem; line-height: 1; }
</style>
