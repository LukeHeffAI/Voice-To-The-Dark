<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import type { Folder, StoryListItem } from '../api/types'
import { usePlaylistStore } from '../stores/playlist'
import { useNotificationStore } from '../stores/notifications'
import * as storiesApi from '../api/stories'

const props = defineProps<{
  story: StoryListItem
  folders: Folder[]
  folderContext?: { folderId: number }
}>()

const emit = defineEmits<{ close: []; removed: [] }>()

const playlist = usePlaylistStore()
const notifications = useNotificationStore()
const showFolderSub = ref(false)
const newFolderName = ref('')
const menuEl = ref<HTMLElement>()

function addToQueue() {
  playlist.addToEnd({
    storyId: props.story.id,
    title: props.story.title,
    author: props.story.author || '',
  })
  notifications.show('Added to queue', 'success')
  emit('close')
}

function playNext() {
  playlist.addNext({
    storyId: props.story.id,
    title: props.story.title,
    author: props.story.author || '',
  })
  notifications.show('Playing next', 'success')
  emit('close')
}

async function addToFolder(folderId: number) {
  try {
    await storiesApi.addStoryToFolder(folderId, props.story.id)
    notifications.show('Added to folder', 'success')
  } catch {
    notifications.show('Failed to add to folder', 'error')
  }
  emit('close')
}

async function createAndAdd() {
  const name = newFolderName.value.trim()
  if (!name) return
  try {
    const folder = await storiesApi.createFolder(name)
    await storiesApi.addStoryToFolder(folder.id, props.story.id)
    notifications.show(`Added to "${name}"`, 'success')
  } catch (e) {
    notifications.show(e instanceof Error ? e.message : 'Failed', 'error')
  }
  emit('close')
}

async function hideFromHome() {
  try {
    await storiesApi.hideStory(props.story.id)
    notifications.show('Removed from home', 'success')
    emit('removed')
  } catch {
    notifications.show('Failed to hide', 'error')
  }
  emit('close')
}

async function removeFromFolder() {
  if (!props.folderContext) return
  try {
    await storiesApi.removeStoryFromFolder(props.folderContext.folderId, props.story.id)
    notifications.show('Removed from folder', 'success')
    emit('removed')
  } catch {
    notifications.show('Failed to remove', 'error')
  }
  emit('close')
}

function onClickOutside(e: Event) {
  if (menuEl.value && !menuEl.value.contains(e.target as Node)) {
    emit('close')
  }
}

onMounted(() => {
  setTimeout(() => document.addEventListener('click', onClickOutside), 0)
})
onUnmounted(() => {
  document.removeEventListener('click', onClickOutside)
})
</script>

<template>
  <div ref="menuEl" class="card-menu">
    <!-- Folder submenu -->
    <button class="menu-item" @click.stop="showFolderSub = !showFolderSub">
      Add to folder ›
    </button>
    <div v-if="showFolderSub" class="folder-sub">
      <button
        v-for="f in folders"
        :key="f.id"
        class="menu-item sub-item"
        @click.stop="addToFolder(f.id)"
      >
        {{ f.name }}
      </button>
      <div class="new-folder-row">
        <input
          v-model="newFolderName"
          class="new-folder-input"
          placeholder="New folder"
          @keyup.enter="createAndAdd"
          @click.stop
        />
        <button v-if="newFolderName.trim()" class="new-folder-ok" @click.stop="createAndAdd">
          OK
        </button>
      </div>
    </div>

    <!-- Queue actions (only if audio exists) -->
    <template v-if="story.has_audio">
      <button class="menu-item" @click="addToQueue">Add to Queue</button>
      <button class="menu-item" @click="playNext">Play Next</button>
    </template>

    <!-- Context-dependent actions -->
    <button v-if="folderContext" class="menu-item danger" @click="removeFromFolder">
      Remove from folder
    </button>
    <button v-else class="menu-item" @click="hideFromHome">Remove from recent</button>
  </div>
</template>

<style scoped>
.card-menu {
  position: absolute;
  right: 0;
  top: 100%;
  min-width: 180px;
  background: #141414;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  padding: 0.35rem 0;
  z-index: 50;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
}

.menu-item {
  display: block;
  width: 100%;
  text-align: left;
  padding: 0.5rem 0.9rem;
  background: none;
  border: none;
  color: #e8e6e3;
  font-size: 0.78rem;
  cursor: pointer;
  transition: background 0.1s;
}
.menu-item:hover {
  background: rgba(255, 255, 255, 0.04);
}
.menu-item.danger:hover {
  background: rgba(204, 68, 68, 0.1);
  color: #e07070;
}
.menu-item.sub-item {
  padding-left: 1.2rem;
  color: #8a8a8a;
}
.menu-item.sub-item:hover {
  color: #e8e6e3;
}

.folder-sub {
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  padding: 0.25rem 0;
}

.new-folder-row {
  display: flex;
  gap: 0.3rem;
  padding: 0.35rem 0.9rem;
}
.new-folder-input {
  flex: 1;
  padding: 0.3rem 0.5rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  color: #e8e6e3;
  font-size: 0.75rem;
  font-family: inherit;
}
.new-folder-input:focus {
  outline: none;
  border-color: rgba(160, 32, 32, 0.4);
}
.new-folder-ok {
  padding: 0.3rem 0.5rem;
  background: var(--color-accent);
  border: none;
  border-radius: 6px;
  color: white;
  font-size: 0.7rem;
  cursor: pointer;
}
</style>
