<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { foldersApi } from '@/api/client'
import { usePlaylistStore } from '@/stores/playlist'
import { useNotificationStore } from '@/stores/notifications'
import type { StoryListItem, Folder } from '@/types'
import FolderPills from '@/components/FolderPills.vue'
import StoryCard from '@/components/StoryCard.vue'

const route = useRoute()
const router = useRouter()
const playlist = usePlaylistStore()
const notify = useNotificationStore()

const folderName = ref('')
const stories = ref<StoryListItem[]>([])
const folders = ref<Folder[]>([])
const loading = ref(true)
const folderId = ref(0)

async function loadFolder() {
  folderId.value = Number(route.params.id)
  loading.value = true
  try {
    const allFolders = await foldersApi.list()
    folders.value = allFolders
    const folder = allFolders.find((f) => f.id === folderId.value)
    folderName.value = folder?.name || 'Folder'

    stories.value = await foldersApi.listStories(folderId.value)
  } catch {
    notify.show('Failed to load folder', 'error')
  } finally {
    loading.value = false
  }
}

onMounted(loadFolder)
watch(() => route.params.id, loadFolder)

async function deleteFolder() {
  if (!confirm('Delete this folder? Stories will not be deleted.')) return
  try {
    await foldersApi.delete(folderId.value)
    notify.show('Folder deleted')
    router.push('/')
  } catch {
    notify.show('Failed to delete folder', 'error')
  }
}

async function removeFromFolder(_fid: number, storyId: number) {
  try {
    await foldersApi.removeStory(folderId.value, storyId)
    stories.value = stories.value.filter((s) => s.id !== storyId)
    notify.show('Removed from folder')
  } catch {
    notify.show('Failed to remove story', 'error')
  }
}

function addToQueue(story: StoryListItem) {
  playlist.addToEnd({ storyId: story.id, title: story.title, author: story.author || '' })
  notify.show('Added to queue')
}

function playNext(story: StoryListItem) {
  playlist.addNext({ storyId: story.id, title: story.title, author: story.author || '' })
  notify.show('Playing next')
}
</script>

<template>
  <div class="page-container">
    <router-link to="/" class="back-link">&larr; Home</router-link>

    <div class="folder-header">
      <h1 class="folder-title">{{ folderName }}</h1>
      <div class="folder-actions">
        <button class="delete-btn" @click="deleteFolder">Delete folder</button>
      </div>
    </div>

    <FolderPills :folders="folders" :active-folder-id="folderId" />

    <div v-if="loading" class="text-center py-8">
      <span class="spinner spinner-lg"></span>
    </div>

    <ul v-else-if="stories.length" class="story-list">
      <li v-for="story in stories" :key="story.id">
        <StoryCard
          :story="story"
          :folder-id="folderId"
          :show-folder-actions="false"
          @remove-from-folder="removeFromFolder"
          @add-to-queue="addToQueue"
          @play-next="playNext"
        />
      </li>
    </ul>

    <div v-else class="empty-state">
      <p>This folder is empty.</p>
      <p>Use the menu on story cards on the <router-link to="/">home page</router-link> to add stories here.</p>
    </div>
  </div>
</template>

<style scoped>
.back-link {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  color: var(--color-text-3);
  text-decoration: none;
  font-size: 0.8rem;
  padding: 0.5rem 0;
  transition: color 0.2s;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}
.back-link:hover { color: var(--color-text-2); }
.folder-header { padding: 1rem 0 1.5rem; }
.folder-title {
  font-family: var(--font-family-serif);
  font-weight: 400;
  font-size: 1.6rem;
  color: var(--color-text-1);
  letter-spacing: 0.08em;
}
.folder-actions { margin-top: 0.75rem; }
.delete-btn {
  padding: 0.4rem 0.9rem;
  border: 1px solid rgba(204,68,68,0.25);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-error);
  font-size: 0.75rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}
.delete-btn:hover {
  background: var(--color-error-dim);
  border-color: var(--color-error);
}
.story-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}
.empty-state { text-align: center; padding: 4rem 1rem; color: var(--color-text-3); }
.empty-state p { margin-top: 0.5rem; font-size: 0.9rem; }
.empty-state a { color: var(--color-accent); text-decoration: none; }
.empty-state a:hover { text-decoration: underline; }
</style>
