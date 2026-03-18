<script setup lang="ts">
import { ref } from 'vue'
import type { StoryListItem, Folder } from '@/types'

defineProps<{
  story: StoryListItem
  folders?: Folder[]
  showFolderActions?: boolean
  folderId?: number
}>()

const emit = defineEmits<{
  close: []
  hide: []
  removeFromFolder: []
  addToFolder: [folderId: number]
  addToQueue: []
  playNext: []
  createFolderAndAdd: [name: string]
}>()

const newFolderName = ref('')

function doCreateFolder() {
  const name = newFolderName.value.trim()
  if (!name) return
  emit('createFolderAndAdd', name)
  emit('close')
}

function doAction(action: () => void) {
  action()
  emit('close')
}
</script>

<template>
  <div class="card-dropdown">
    <!-- Folder actions (home page) -->
    <template v-if="showFolderActions !== false && folders?.length">
      <span class="dropdown-label">Add to folder</span>
      <button
        v-for="f in folders"
        :key="f.id"
        class="dropdown-item"
        @click="doAction(() => emit('addToFolder', f.id))"
      >
        <span class="dropdown-icon">&#9776;</span> {{ f.name }}
      </button>
      <div class="new-folder-row">
        <input
          v-model="newFolderName"
          type="text"
          class="new-folder-input"
          placeholder="New folder..."
          maxlength="60"
          @keydown.enter="doCreateFolder"
        />
        <button class="new-folder-ok" @click="doCreateFolder">+</button>
      </div>
    </template>

    <!-- Queue actions -->
    <template v-if="story.has_audio">
      <div v-if="showFolderActions !== false && folders?.length" class="dropdown-separator"></div>
      <button class="dropdown-item" @click="doAction(() => emit('addToQueue'))">
        <span class="dropdown-icon">+</span> Add to Queue
      </button>
      <button class="dropdown-item" @click="doAction(() => emit('playNext'))">
        <span class="dropdown-icon">&#9654;</span> Play Next
      </button>
    </template>

    <!-- Remove from folder (folder page) -->
    <template v-if="folderId">
      <div class="dropdown-separator"></div>
      <button class="dropdown-item danger" @click="doAction(() => emit('removeFromFolder'))">
        <span class="dropdown-icon">&#10005;</span> Remove from folder
      </button>
    </template>

    <!-- Hide from home -->
    <template v-if="!folderId">
      <div class="dropdown-separator"></div>
      <button class="dropdown-item danger" @click="doAction(() => emit('hide'))">
        <span class="dropdown-icon">&#10005;</span> Remove from recent
      </button>
    </template>
  </div>
</template>

<style scoped>
.card-dropdown {
  position: absolute; top: calc(50% + 18px); right: 0.6rem;
  min-width: 200px; background: #161616; border: 1px solid var(--color-border-hover);
  border-radius: var(--radius-md); padding: 0.35rem 0; z-index: 100;
  box-shadow: 0 8px 32px rgba(0,0,0,0.5);
}
.dropdown-label {
  display: block; padding: 0.4rem 1rem 0.25rem; font-size: 0.65rem;
  font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--color-text-3);
}
.dropdown-item {
  display: flex; align-items: center; gap: 0.6rem; width: 100%;
  padding: 0.6rem 1rem; border: none; background: none;
  color: var(--color-text-2); font-family: var(--font-family-serif); font-size: 0.8rem;
  cursor: pointer; text-align: left; transition: all 0.15s; white-space: nowrap;
}
.dropdown-item:hover { background: var(--color-surface-hover); color: var(--color-text-1); }
.dropdown-item.danger { color: var(--color-error); }
.dropdown-item.danger:hover { background: var(--color-error-dim); }
.dropdown-icon { width: 14px; text-align: center; font-size: 0.85rem; flex-shrink: 0; }
.dropdown-separator { height: 1px; background: var(--color-border); margin: 0.3rem 0; }
.new-folder-row { display: flex; align-items: center; gap: 0.4rem; padding: 0.35rem 0.6rem; }
.new-folder-input {
  flex: 1; padding: 0.3rem 0.5rem; background: var(--color-surface);
  border: 1px solid var(--color-border); border-radius: var(--radius-sm);
  color: var(--color-text-1); font-family: var(--font-family-sans); font-size: 0.75rem; outline: none;
}
.new-folder-input:focus { border-color: var(--color-border-focus); }
.new-folder-input::placeholder { color: var(--color-text-3); }
.new-folder-ok {
  padding: 0.25rem 0.5rem; background: var(--color-accent); border: none;
  border-radius: var(--radius-sm); color: #fff; font-size: 0.7rem; font-weight: 600; cursor: pointer;
}
</style>
