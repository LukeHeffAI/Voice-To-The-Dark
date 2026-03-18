<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { Folder, StoryListItem } from '../api/types'
import * as storiesApi from '../api/stories'
import { useNotificationStore } from '../stores/notifications'
import StoryCard from '../components/StoryCard.vue'
import FolderNav from '../components/FolderNav.vue'

const route = useRoute()
const router = useRouter()
const notifications = useNotificationStore()

const folderId = computed(() => Number(route.params.id))
const folders = ref<Folder[]>([])
const stories = ref<StoryListItem[]>([])
const loading = ref(true)
const currentFolder = computed(() => folders.value.find((f) => f.id === folderId.value))

async function loadData() {
  loading.value = true
  try {
    folders.value = await storiesApi.listFolders()
    stories.value = await storiesApi.listStories(0, 100)
  } catch {
    notifications.show('Failed to load folder', 'error')
  } finally {
    loading.value = false
  }
}

async function deleteThisFolder() {
  if (!confirm(`Delete folder "${currentFolder.value?.name}"?`)) return
  try {
    await storiesApi.deleteFolder(folderId.value)
    notifications.show('Folder deleted', 'success')
    router.push({ name: 'home' })
  } catch {
    notifications.show('Failed to delete folder', 'error')
  }
}

function onFolderSelect(id: number | null) {
  if (id === null) {
    router.push({ name: 'home' })
  } else {
    router.push({ name: 'folder', params: { id } })
  }
}

function onStoryRemoved() {
  loadData()
}

onMounted(loadData)
</script>

<template>
  <div>
    <RouterLink to="/" class="back-link">← Back to stories</RouterLink>

    <div class="folder-header">
      <h1 class="folder-title">{{ currentFolder?.name || 'Folder' }}</h1>
      <button class="delete-btn" @click="deleteThisFolder">Delete folder</button>
    </div>

    <div class="folder-section">
      <FolderNav :folders="folders" :active-id="folderId" @select="onFolderSelect" />
    </div>

    <div v-if="loading" class="loading">Loading...</div>
    <div v-else-if="stories.length === 0" class="empty">No stories in this folder</div>
    <div v-else class="story-list">
      <StoryCard
        v-for="story in stories"
        :key="story.id"
        :story="story"
        :folders="folders"
        :folder-context="{ folderId: folderId }"
        @removed="onStoryRemoved"
      />
    </div>
  </div>
</template>

<style scoped>
.back-link {
  display: inline-block;
  color: #555;
  text-decoration: none;
  font-size: 0.8rem;
  margin-bottom: 1rem;
  transition: color 0.15s;
}
.back-link:hover {
  color: #8a8a8a;
}

.folder-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
}
.folder-title {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 1.6rem;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.9);
}
.delete-btn {
  background: none;
  border: 1px solid rgba(204, 68, 68, 0.2);
  color: #c44;
  font-size: 0.75rem;
  padding: 0.35rem 0.7rem;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s;
}
.delete-btn:hover {
  background: rgba(204, 68, 68, 0.1);
}

.folder-section {
  margin-bottom: 1.25rem;
}

.story-list {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.loading,
.empty {
  text-align: center;
  padding: 3rem;
  color: #555;
  font-size: 0.85rem;
}
</style>
