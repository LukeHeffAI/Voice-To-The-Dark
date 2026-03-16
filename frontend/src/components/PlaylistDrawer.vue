<script setup lang="ts">
import { usePlaylistStore } from '../stores/playlist'
import draggable from 'vuedraggable'

defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()

const playlist = usePlaylistStore()

function onDragEnd(evt: { oldIndex?: number; newIndex?: number }) {
  if (evt.oldIndex !== undefined && evt.newIndex !== undefined) {
    playlist.reorder(evt.oldIndex, evt.newIndex)
  }
}
</script>

<template>
  <!-- Backdrop -->
  <div v-if="open" class="drawer-backdrop" @click="emit('close')" />

  <!-- Drawer -->
  <div class="playlist-drawer" :class="{ open }">
    <div class="drawer-header">
      <span class="drawer-title">Queue</span>
      <button v-if="playlist.items.length > 0" class="drawer-clear" @click="playlist.clear()">
        Clear all
      </button>
    </div>

    <div v-if="playlist.items.length === 0" class="drawer-empty">Queue is empty</div>

    <draggable
      v-else
      :list="playlist.items"
      item-key="storyId"
      handle=".drag-handle"
      ghost-class="sortable-ghost"
      tag="ul"
      class="drawer-list"
      @end="onDragEnd"
    >
      <template #item="{ element, index }">
        <li
          class="drawer-item"
          :class="{ 'now-playing': index === playlist.currentIndex }"
          @click="playlist.playAt(index)"
        >
          <span class="drag-handle">⠿</span>
          <div class="drawer-item-info">
            <div class="drawer-item-title">
              {{ element.title || 'Untitled' }}
              <span v-if="index === playlist.currentIndex" class="now-badge">Now</span>
            </div>
            <div class="drawer-item-author">{{ element.author || 'Unknown' }}</div>
          </div>
          <button
            class="drawer-item-remove"
            @click.stop="playlist.removeAt(index)"
            title="Remove"
          >
            ✕
          </button>
        </li>
      </template>
    </draggable>
  </div>
</template>

<style scoped>
.drawer-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  z-index: 8998;
}

.playlist-drawer {
  position: fixed;
  bottom: 56px;
  left: 0;
  right: 0;
  max-height: 60vh;
  background: #0e0e0e;
  border-top: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 16px 16px 0 0;
  z-index: 8999;
  transform: translateY(100%);
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  display: flex;
  flex-direction: column;
}
.playlist-drawer.open {
  transform: translateY(0);
}

.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem 0.75rem;
  flex-shrink: 0;
}
.drawer-title {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 1.1rem;
  font-weight: 500;
  color: #e8e6e3;
  letter-spacing: 0.04em;
}
.drawer-clear {
  background: none;
  border: none;
  color: #555;
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 0.75rem;
  cursor: pointer;
  padding: 0.3rem 0.6rem;
  border-radius: 6px;
  transition: all 0.15s;
}
.drawer-clear:hover {
  color: #c44;
  background: rgba(204, 68, 68, 0.1);
}

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
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}
.drawer-item:hover {
  background: rgba(255, 255, 255, 0.04);
}
.drawer-item.now-playing {
  background: rgba(160, 32, 32, 0.12);
}

.drag-handle {
  color: #555;
  cursor: grab;
  font-size: 1rem;
  padding: 0 0.15rem;
  flex-shrink: 0;
  touch-action: none;
}
.drag-handle:active {
  cursor: grabbing;
}

.drawer-item-info {
  flex: 1;
  min-width: 0;
}
.drawer-item-title {
  font-size: 0.82rem;
  color: #e8e6e3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.drawer-item-author {
  font-size: 0.7rem;
  color: #555;
}
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
  color: #555;
  cursor: pointer;
  padding: 0.3rem;
  font-size: 0.85rem;
  transition: color 0.15s;
  flex-shrink: 0;
}
.drawer-item-remove:hover {
  color: #c44;
}

.drawer-empty {
  text-align: center;
  padding: 2rem 1rem;
  color: #555;
  font-size: 0.85rem;
}

:deep(.sortable-ghost) {
  opacity: 0.4;
  background: rgba(255, 255, 255, 0.04);
}
</style>
