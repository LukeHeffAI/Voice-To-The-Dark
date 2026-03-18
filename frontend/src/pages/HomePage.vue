<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import type { Folder, StoryListItem } from '../api/types'
import * as storiesApi from '../api/stories'
import { useAuthStore } from '../stores/auth'
import StoryCard from '../components/StoryCard.vue'
import FolderNav from '../components/FolderNav.vue'

const router = useRouter()
const auth = useAuthStore()

const stories = ref<StoryListItem[]>([])
const folders = ref<Folder[]>([])
const activeFolder = ref<number | null>(null)
const loading = ref(true)
const skip = ref(0)
const hasMore = ref(true)
const LIMIT = 25

async function loadStories(append = false) {
  loading.value = true
  try {
    const data = await storiesApi.listStories(skip.value, LIMIT)
    if (append) {
      stories.value.push(...data)
    } else {
      stories.value = data
    }
    hasMore.value = data.length === LIMIT
  } catch {
    // Silent fail on list
  } finally {
    loading.value = false
  }
}

async function loadFolders() {
  if (!auth.isAuthenticated) return
  try {
    folders.value = await storiesApi.listFolders()
  } catch {
    // Not critical
  }
}

function loadMore() {
  skip.value += LIMIT
  loadStories(true)
}

function onFolderSelect(folderId: number | null) {
  activeFolder.value = folderId
}

function onStoryRemoved() {
  // Refresh list
  skip.value = 0
  loadStories()
}

watch(activeFolder, (id) => {
  if (id !== null) {
    router.push({ name: 'folder', params: { id } })
  }
})

// Load folders once auth is ready (auth.init() may complete after mount)
watch(() => auth.isAuthenticated, (isAuth) => {
  if (isAuth) {
    loadFolders()
  }
})

onMounted(() => {
  loadStories()
  loadFolders()
})
</script>

<template>
  <div>
    <!-- Hero -->
    <div class="hero">
      <h1 class="hero-title">Voice In The Dark</h1>
      <p class="hero-subtitle">Horror stories, dramatically narrated.</p>
    </div>

    <!-- Folder navigation -->
    <div v-if="folders.length > 0" class="folder-section">
      <FolderNav :folders="folders" :active-id="activeFolder" @select="onFolderSelect" />
    </div>

    <!-- Story list -->
    <div class="story-list">
      <StoryCard
        v-for="story in stories"
        :key="story.id"
        :story="story"
        :folders="folders"
        @removed="onStoryRemoved"
      />
    </div>

    <!-- Loading / Load more -->
    <div v-if="loading" class="loading-indicator">Loading...</div>
    <div v-else-if="stories.length === 0" class="empty-state">No stories yet</div>
    <button v-else-if="hasMore" class="load-more-btn" @click="loadMore">Load more</button>
  </div>
</template>

<style scoped>
.hero {
  text-align: center;
  padding: 2rem 0 1.5rem;
}
.hero-title {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 2.2rem;
  font-weight: 400;
  color: rgba(255, 255, 255, 0.9);
  letter-spacing: 0.03em;
}
.hero-subtitle {
  color: #555;
  font-size: 0.9rem;
  margin-top: 0.25rem;
}

.folder-section {
  margin-bottom: 1.25rem;
}

.story-list {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.loading-indicator {
  text-align: center;
  padding: 2rem;
  color: #555;
  font-size: 0.85rem;
}

.empty-state {
  text-align: center;
  padding: 3rem;
  color: #555;
  font-size: 0.9rem;
}

.load-more-btn {
  display: block;
  width: 100%;
  padding: 0.75rem;
  margin-top: 1rem;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 10px;
  color: #8a8a8a;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.15s;
}
.load-more-btn:hover {
  background: rgba(255, 255, 255, 0.045);
  color: #e8e6e3;
}
</style>
