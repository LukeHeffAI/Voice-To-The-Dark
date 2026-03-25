<script setup lang="ts">
import { ref, watch, nextTick, onUnmounted } from 'vue'
import { usePlaylistStore } from '@/stores/playlist'
import Sortable from 'sortablejs'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()

const playlist = usePlaylistStore()
const listEl = ref<HTMLElement>()
let sortableInstance: Sortable | null = null

function initSortable() {
  if (sortableInstance) sortableInstance.destroy()
  if (!listEl.value) return
  sortableInstance = Sortable.create(listEl.value, {
    handle: '.drag-handle',
    animation: 150,
    ghostClass: 'sortable-ghost',
    onEnd(evt) {
      if (evt.oldIndex !== undefined && evt.newIndex !== undefined) {
        playlist.reorder(evt.oldIndex, evt.newIndex)
      }
    },
  })
}

watch(
  () => props.open,
  async (isOpen) => {
    if (isOpen) {
      await nextTick()
      initSortable()
    }
  },
)

onUnmounted(() => {
  if (sortableInstance) sortableInstance.destroy()
})

function clearAndClose() {
  playlist.clear()
  emit('close')
}
</script>

<template>
  <!-- Backdrop -->
  <div v-if="open" class="drawer-backdrop" @click="emit('close')"></div>

  <!-- Drawer -->
  <div class="playlist-drawer" :class="{ open }">
    <div class="drawer-header">
      <span class="drawer-title">Queue</span>
      <button class="drawer-clear" @click="clearAndClose">Clear all</button>
    </div>

    <ul ref="listEl" class="drawer-list">
      <li v-if="playlist.items.length === 0" class="drawer-empty">
        Queue is empty. Add stories from the story list.
      </li>
      <li
        v-for="(item, idx) in playlist.items"
        :key="item.storyId + '-' + idx"
        class="drawer-item"
        :class="{ 'now-playing': idx === playlist.currentIndex }"
      >
        <span class="drag-handle">&#9776;</span>
        <div class="drawer-item-info" @click="playlist.playAt(idx)">
          <div class="drawer-item-title">
            {{ item.title || 'Untitled' }}
            <span v-if="idx === playlist.currentIndex" class="now-badge">Playing</span>
          </div>
          <div class="drawer-item-author">{{ item.author ? 'u/' + item.author : '' }}</div>
        </div>
        <button class="drawer-item-remove" title="Remove" @click.stop="playlist.removeAt(idx)">&times;</button>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.drawer-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.6);
  z-index: 8998;
}
.playlist-drawer {
  position: fixed;
  bottom: 56px;
  left: 0;
  right: 0;
  max-height: 60vh;
  background: #0e0e0e;
  border-top: 1px solid var(--color-border-hover);
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  z-index: 8999;
  transform: translateY(100%);
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  display: flex;
  flex-direction: column;
}
.playlist-drawer.open { transform: translateY(0); }
.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem 0.75rem;
  flex-shrink: 0;
}
.drawer-title {
  font-family: var(--font-family-serif);
  font-size: 1.1rem;
  font-weight: 500;
  color: var(--color-text-1);
  letter-spacing: 0.04em;
}
.drawer-clear {
  background: none;
  border: none;
  color: var(--color-text-3);
  font-family: var(--font-family-serif);
  font-size: 0.75rem;
  cursor: pointer;
  padding: 0.3rem 0.6rem;
  border-radius: var(--radius-sm);
  transition: all 0.15s;
}
.drawer-clear:hover { color: var(--color-error); background: var(--color-error-dim); }
.drawer-list {
  list-style: none;
  overflow-y: auto;
  padding: 0 0.75rem 0.75rem;
  flex: 1;
}
.drawer-item {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.6rem 0.5rem;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.15s;
}
.drawer-item:hover { background: var(--color-surface-hover); }
.drawer-item.now-playing { background: var(--color-accent-dim); }
.drag-handle {
  color: var(--color-text-3);
  cursor: grab;
  font-size: 1rem;
  padding: 0 0.15rem;
  flex-shrink: 0;
  touch-action: none;
}
.drag-handle:active { cursor: grabbing; }
.drawer-item-info { flex: 1; min-width: 0; }
.drawer-item-title {
  font-size: 0.82rem;
  color: var(--color-text-1);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.drawer-item-author { font-size: 0.7rem; color: var(--color-text-3); }
.now-badge {
  font-size: 0.6rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--color-accent);
  margin-left: 0.4rem;
}
.drawer-item-remove {
  background: none;
  border: none;
  color: var(--color-text-3);
  cursor: pointer;
  padding: 0.3rem;
  font-size: 0.85rem;
  transition: color 0.15s;
  flex-shrink: 0;
}
.drawer-item-remove:hover { color: var(--color-error); }
.drawer-empty {
  text-align: center;
  padding: 2rem 1rem;
  color: var(--color-text-3);
  font-size: 0.85rem;
}
</style>
