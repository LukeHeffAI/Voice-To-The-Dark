<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import type { Story } from '../api/types'
import * as storiesApi from '../api/stories'
import { useNotificationStore } from '../stores/notifications'
import SeriesParts from '../components/SeriesParts.vue'

const route = useRoute()
const notifications = useNotificationStore()

const storyId = computed(() => Number(route.params.id))
const story = ref<Story | null>(null)
const loading = ref(true)
const readingProgress = ref(0)

async function loadStory() {
  loading.value = true
  try {
    story.value = await storiesApi.getStory(storyId.value)
    await nextTick()
    restoreScrollPosition()
  } catch {
    notifications.show('Story not found', 'error')
  } finally {
    loading.value = false
  }
}

const paragraphs = computed(() => {
  if (!story.value?.narration_text) return []
  return story.value.narration_text
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean)
})

const wordCount = computed(() => {
  if (!story.value?.narration_text) return 0
  return story.value.narration_text.split(/\s+/).filter(Boolean).length
})

const readMinutes = computed(() => {
  return Math.max(1, Math.round(wordCount.value / 250))
})

// Reading progress
function updateProgress() {
  const docHeight = document.documentElement.scrollHeight - window.innerHeight
  if (docHeight <= 0) {
    readingProgress.value = 100
    return
  }
  readingProgress.value = Math.min(100, (window.scrollY / docHeight) * 100)
}

// Scroll position persistence
const storageKey = computed(() => `vttd_read_pos_${storyId.value}`)
let scrollSaveTimer: ReturnType<typeof setTimeout> | null = null

function saveScrollPosition() {
  const docHeight = document.documentElement.scrollHeight - window.innerHeight
  if (docHeight <= 0) return
  const pct = window.scrollY / docHeight
  localStorage.setItem(storageKey.value, pct.toFixed(4))
}

function restoreScrollPosition() {
  const saved = parseFloat(localStorage.getItem(storageKey.value) || '0')
  if (saved > 0.01 && saved < 0.99) {
    const docHeight = document.documentElement.scrollHeight - window.innerHeight
    window.scrollTo(0, Math.round(saved * docHeight))
  }
}

function onScroll() {
  updateProgress()
  if (scrollSaveTimer) clearTimeout(scrollSaveTimer)
  scrollSaveTimer = setTimeout(saveScrollPosition, 300)
}

onMounted(() => {
  window.addEventListener('scroll', onScroll, { passive: true })
  window.addEventListener('beforeunload', saveScrollPosition)
  loadStory()
})

onUnmounted(() => {
  window.removeEventListener('scroll', onScroll)
  window.removeEventListener('beforeunload', saveScrollPosition)
  if (scrollSaveTimer) clearTimeout(scrollSaveTimer)
  saveScrollPosition()
})
</script>

<template>
  <div class="reading-progress" :style="{ width: readingProgress + '%' }" />

  <div v-if="loading" class="loading">Loading story...</div>
  <div v-else-if="story" class="reader-container">
    <RouterLink :to="{ name: 'story-detail', params: { id: storyId } }" class="back-link">
      &larr; Story details
    </RouterLink>

    <div class="reader-header">
      <div class="reader-title">{{ story.title }}</div>
      <div class="reader-meta">
        <span v-if="story.author">by u/{{ story.author }}</span>
        <a v-if="story.reddit_url" :href="story.reddit_url" target="_blank" rel="noopener">
          View on Reddit
        </a>
      </div>
      <div class="reader-stats">
        <div v-if="wordCount" class="reader-stat">
          <span class="reader-stat-value">{{ wordCount.toLocaleString() }}</span> words
        </div>
        <div v-if="readMinutes" class="reader-stat">
          ~<span class="reader-stat-value">{{ readMinutes }}</span> min read
        </div>
      </div>
    </div>

    <div class="reader-body">
      <template v-for="(para, i) in paragraphs" :key="i">
        <hr v-if="para === '---'" />
        <p v-else>{{ para }}</p>
      </template>
    </div>

    <SeriesParts :story-id="storyId" />

    <div class="reader-footer">
      <RouterLink :to="{ name: 'story-detail', params: { id: storyId } }" class="btn-secondary">
        &larr; Story Details
      </RouterLink>
      <RouterLink
        v-if="story.audio_file_path"
        :to="{ name: 'player', params: { id: storyId } }"
        class="btn-secondary"
      >
        &#9654; Listen
      </RouterLink>
    </div>
  </div>
</template>

<style scoped>
.reading-progress {
  position: fixed;
  top: 0;
  left: 0;
  height: 2px;
  background: var(--color-accent);
  box-shadow: 0 0 8px rgba(160, 32, 32, 0.4);
  z-index: 9998;
  transition: width 0.1s linear;
}

.loading {
  text-align: center;
  padding: 3rem;
  color: #555;
}

.reader-container {
  max-width: 640px;
  margin: 0 auto;
}

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

/* Header */
.reader-header {
  padding: 2.5rem 0 2rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  margin-bottom: 2.5rem;
  text-align: center;
}
.reader-title {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 2rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
  line-height: 1.25;
}
.reader-meta {
  font-size: 0.8rem;
  color: #555;
  margin-top: 0.6rem;
  display: flex;
  justify-content: center;
  gap: 1rem;
  flex-wrap: wrap;
  letter-spacing: 0.02em;
}
.reader-meta a {
  color: #8a8a8a;
  text-decoration: none;
  transition: color 0.2s;
}
.reader-meta a:hover {
  color: rgba(255, 255, 255, 0.9);
}
.reader-stats {
  display: flex;
  justify-content: center;
  gap: 1.5rem;
  margin-top: 0.75rem;
  flex-wrap: wrap;
}
.reader-stat {
  font-size: 0.75rem;
  color: #555;
  letter-spacing: 0.02em;
}
.reader-stat-value {
  color: #8a8a8a;
  font-weight: 600;
}

/* Story text */
.reader-body {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 1.2rem;
  font-weight: 400;
  color: rgba(255, 255, 255, 0.9);
  line-height: 1.85;
  letter-spacing: 0.01em;
  padding-bottom: 4rem;
}
.reader-body p {
  margin-bottom: 1.4em;
  text-indent: 0;
}
.reader-body p:first-child {
  font-size: 1.25rem;
}
.reader-body p:first-child::first-letter {
  font-size: 3.2em;
  float: left;
  line-height: 0.8;
  margin: 0.06em 0.12em 0 0;
  color: var(--color-accent);
  font-weight: 700;
  font-family: 'Cormorant Garamond', Georgia, serif;
}

.reader-body hr {
  border: none;
  text-align: center;
  margin: 2.5rem 0;
  color: #555;
  font-size: 1rem;
  letter-spacing: 0.5em;
}
.reader-body hr::after {
  content: '\2022  \2022  \2022';
}

/* Footer */
.reader-footer {
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  padding: 2rem 0;
  display: flex;
  justify-content: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.btn-secondary {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.55rem 1rem;
  border-radius: 8px;
  font-size: 0.8rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  text-decoration: none;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: #e8e6e3;
}
.btn-secondary:hover {
  background: rgba(255, 255, 255, 0.06);
}
</style>
