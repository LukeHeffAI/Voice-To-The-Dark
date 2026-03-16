<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { storiesApi, foldersApi } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { usePlaylistStore } from '@/stores/playlist'
import { useNotificationStore } from '@/stores/notifications'
import type { StoryListItem, Folder } from '@/types'
import FolderPills from '@/components/FolderPills.vue'
import StoryCard from '@/components/StoryCard.vue'

const auth = useAuthStore()
const playlist = usePlaylistStore()
const notify = useNotificationStore()

const stories = ref<StoryListItem[]>([])
const folders = ref<Folder[]>([])
const loading = ref(true)

onMounted(async () => {
  try {
    const [storiesData, foldersData] = await Promise.all([
      storiesApi.list(0, 50),
      auth.isLoggedIn ? foldersApi.list() : Promise.resolve([]),
    ])
    stories.value = storiesData
    folders.value = foldersData
  } catch {
    notify.show('Failed to load stories', 'error')
  } finally {
    loading.value = false
  }
})

async function hideStory(storyId: number) {
  try {
    await storiesApi.hide(storyId)
    stories.value = stories.value.filter((s) => s.id !== storyId)
    notify.show('Removed from recent')
  } catch {
    notify.show('Failed to hide story', 'error')
  }
}

async function addToFolder(folderId: number, storyId: number) {
  try {
    await foldersApi.addStory(folderId, storyId)
    const folder = folders.value.find((f) => f.id === folderId)
    notify.show(`Added to ${folder?.name || 'folder'}`)
  } catch {
    notify.show('Failed to add to folder', 'error')
  }
}

async function createFolderAndAdd(folderName: string, storyId: number) {
  try {
    const folder = await foldersApi.create(folderName)
    await foldersApi.addStory(folder.id, storyId)
    folders.value.push(folder)
    notify.show(`Created "${folder.name}" and added story`)
  } catch {
    notify.show('Failed to create folder', 'error')
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
  <div class="page-home">
    <!-- Hero -->
    <div class="hero">
      <h1>Voice In The Dark</h1>
    </div>

    <!-- Submit link -->
    <router-link to="/submit" class="submit-link">+ Hear a new tale</router-link>

    <!-- Folder navigation -->
    <div class="content-area">
      <FolderPills v-if="auth.isLoggedIn && folders.length" :folders="folders" />

      <div v-if="stories.length" class="section-header">
        <span class="section-title">Recently Viewed</span>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="text-center py-8">
        <span class="spinner spinner-lg"></span>
      </div>

      <!-- Story list -->
      <ul v-else-if="stories.length" class="story-list">
        <li v-for="story in stories" :key="story.id">
          <StoryCard
            :story="story"
            :folders="folders"
            :show-folder-actions="auth.isLoggedIn"
            @hide="hideStory"
            @add-to-folder="addToFolder"
            @create-folder-and-add="createFolderAndAdd"
            @add-to-queue="addToQueue"
            @play-next="playNext"
          />
        </li>
      </ul>

      <!-- Empty state -->
      <div v-else class="empty-state">
        <p>No stories yet.</p>
        <p><router-link to="/submit">Submit a NoSleep story</router-link> to get started.</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-home { padding: 1.25rem; position: relative; z-index: 3; }
.hero {
  text-align: center;
  padding: 3rem 0 2.5rem;
  border-bottom: 1px solid var(--color-border);
  margin-bottom: 2rem;
}
.hero h1 {
  font-family: var(--font-family-serif);
  font-weight: 300;
  font-size: 2.2rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-text-1);
  line-height: 1.2;
}
.submit-link {
  display: block;
  max-width: 640px;
  margin: 0 auto 2rem;
  text-align: center;
  padding: 0.85rem 1.5rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  color: var(--color-text-3);
  text-decoration: none;
  font-family: var(--font-family-serif);
  font-size: 1.3rem;
  font-weight: 500;
  letter-spacing: 0.04em;
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.submit-link:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
  background: var(--color-accent-dim);
  box-shadow: 0 0 30px rgba(160,32,32,0.2);
}
.content-area { max-width: 640px; margin: 0 auto; }
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
}
.section-title {
  font-family: var(--font-family-serif);
  font-size: 1.1rem;
  font-weight: 400;
  color: var(--color-text-2);
  letter-spacing: 0.08em;
  text-transform: uppercase;
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
