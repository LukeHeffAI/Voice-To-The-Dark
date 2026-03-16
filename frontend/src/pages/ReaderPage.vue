<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { storiesApi } from '@/api/client'
import { useNotificationStore } from '@/stores/notifications'
import type { Story, SeriesPart } from '@/types'

const route = useRoute()
const notify = useNotificationStore()

const storyId = computed(() => Number(route.params.id))
const story = ref<Story | null>(null)
const loading = ref(true)
const progressWidth = ref('0%')
const seriesParts = ref<SeriesPart[]>([])

// ── Computed content ──────────────────────────────────────
const paragraphs = computed(() => {
  if (!story.value?.narration_text) return []
  return story.value.narration_text
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter((p) => p.length > 0)
})

const wordCount = computed(() => {
  if (!story.value?.narration_text) return 0
  return story.value.narration_text.split(/\s+/).filter((w) => w.length > 0).length
})

const readMinutes = computed(() => {
  return Math.max(1, Math.round(wordCount.value / 250))
})

// ── Reading progress ──────────────────────────────────────
function updateProgress() {
  const docHeight = document.documentElement.scrollHeight - window.innerHeight
  if (docHeight <= 0) {
    progressWidth.value = '100%'
    return
  }
  const pct = Math.min(100, (window.scrollY / docHeight) * 100)
  progressWidth.value = `${pct}%`
}

// ── Scroll position persistence ───────────────────────────
const storageKey = computed(() => `vttd_read_pos_${storyId.value}`)
let scrollSaveTimer: ReturnType<typeof setTimeout> | null = null

function saveScrollPosition() {
  const docHeight = document.documentElement.scrollHeight - window.innerHeight
  if (docHeight <= 0) return
  const pct = window.scrollY / docHeight
  localStorage.setItem(storageKey.value, pct.toFixed(4))
}

function restoreScrollPosition() {
  const saved = parseFloat(localStorage.getItem(storageKey.value) || '')
  if (saved && saved > 0.01 && saved < 0.99) {
    const docHeight = document.documentElement.scrollHeight - window.innerHeight
    window.scrollTo(0, Math.round(saved * docHeight))
  }
}

function onScroll() {
  updateProgress()
  if (scrollSaveTimer) clearTimeout(scrollSaveTimer)
  scrollSaveTimer = setTimeout(saveScrollPosition, 300)
}

onMounted(async () => {
  window.addEventListener('scroll', onScroll, { passive: true })
  window.addEventListener('beforeunload', saveScrollPosition)

  try {
    story.value = await storiesApi.get(storyId.value)
  } catch {
    notify.show('Failed to load story', 'error')
    loading.value = false
    return
  }

  // Load series parts
  try {
    const data = await storiesApi.seriesParts(storyId.value)
    if (data.parts && data.parts.length >= 2) {
      seriesParts.value = data.parts
    }
  } catch { /* ignore */ }

  loading.value = false

  // Restore scroll after fonts load (for accurate scroll height)
  if (document.fonts?.ready) {
    document.fonts.ready.then(() => {
      requestAnimationFrame(restoreScrollPosition)
    })
  } else {
    window.addEventListener('load', restoreScrollPosition, { once: true })
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('scroll', onScroll)
  window.removeEventListener('beforeunload', saveScrollPosition)
  saveScrollPosition()
  if (scrollSaveTimer) clearTimeout(scrollSaveTimer)
})

function isCurrentPart(part: SeriesPart): boolean {
  if (!story.value?.reddit_url || !part.url) return false
  return story.value.reddit_url.replace(/\/$/, '') === part.url.replace(/\/$/, '')
}

function isSeparator(text: string): boolean {
  return text === '---' || text === '***' || text === '* * *'
}
</script>

<template>
  <!-- Reading progress bar -->
  <div class="reading-progress" :style="{ width: progressWidth }"></div>

  <div class="reader-container">
    <router-link :to="`/story/${storyId}`" class="back-link">&larr; Story details</router-link>

    <div v-if="loading" class="text-center py-8">
      <span class="spinner spinner-lg"></span>
    </div>

    <template v-else-if="story">
      <div class="reader-header">
        <div class="reader-title">{{ story.title }}</div>
        <div class="reader-meta">
          <span v-if="story.author">by u/{{ story.author }}</span>
          <a v-if="story.reddit_url" :href="story.reddit_url" target="_blank" rel="noopener">View on Reddit</a>
        </div>
        <div class="reader-stats">
          <div v-if="wordCount" class="reader-stat">
            <span class="reader-stat-value">{{ wordCount.toLocaleString() }}</span> words
          </div>
          <div class="reader-stat">
            ~<span class="reader-stat-value">{{ readMinutes }}</span> min read
          </div>
        </div>
      </div>

      <div class="reader-body">
        <template v-for="(para, idx) in paragraphs" :key="idx">
          <hr v-if="isSeparator(para)" />
          <p v-else>{{ para }}</p>
        </template>
      </div>

      <!-- Series parts -->
      <div v-if="seriesParts.length" class="reader-series-nav">
        <div class="reader-series-title">Series Parts</div>
        <ul class="reader-series-list">
          <li v-for="(part, idx) in seriesParts" :key="idx">
            <div v-if="isCurrentPart(part)" class="series-part current">
              <span class="series-part-num">{{ idx + 1 }}</span>
              <span>{{ part.title || `Part ${idx + 1}` }} (current)</span>
            </div>
            <router-link
              v-else-if="part.story_id"
              :to="`/story/${part.story_id}/read`"
              class="series-part"
            >
              <span class="series-part-num">{{ idx + 1 }}</span>
              <span>{{ part.title || `Part ${idx + 1}` }}</span>
            </router-link>
            <div v-else class="series-part" style="opacity: 0.5">
              <span class="series-part-num">{{ idx + 1 }}</span>
              <span>{{ part.title || `Part ${idx + 1}` }} (not fetched)</span>
            </div>
          </li>
        </ul>
      </div>

      <!-- Footer -->
      <div class="reader-footer">
        <router-link :to="`/story/${storyId}`" class="btn-secondary">&larr; Story Details</router-link>
        <router-link v-if="story.audio_file_path" :to="`/story/${storyId}/play`" class="btn-secondary">&#9654; Listen</router-link>
      </div>
    </template>
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

.reader-container { max-width: 640px; margin: 0 auto; padding: 1.25rem; }

/* ── Reading progress bar ────────────────────── */
.reading-progress {
  position: fixed;
  top: 0; left: 0;
  width: 0%;
  height: 2px;
  background: var(--color-accent);
  box-shadow: 0 0 8px rgba(160,32,32,0.4);
  z-index: 9998;
  transition: width 0.1s linear;
}

/* ── Header ──────────────────────────────────── */
.reader-header {
  padding: 2.5rem 0 2rem;
  border-bottom: 1px solid var(--color-border);
  margin-bottom: 2.5rem;
  text-align: center;
}
.reader-title {
  font-family: var(--font-family-serif);
  font-size: 2rem; font-weight: 600;
  color: var(--color-text-1);
  line-height: 1.25;
}
.reader-meta {
  font-size: 0.8rem; color: var(--color-text-3);
  margin-top: 0.6rem;
  display: flex; justify-content: center;
  gap: 1rem; flex-wrap: wrap;
  letter-spacing: 0.02em;
}
.reader-meta a {
  color: var(--color-text-2); text-decoration: none; transition: color 0.2s;
}
.reader-meta a:hover { color: var(--color-text-1); }
.reader-stats {
  display: flex; justify-content: center;
  gap: 1.5rem; margin-top: 0.75rem; flex-wrap: wrap;
}
.reader-stat {
  font-size: 0.75rem; color: var(--color-text-3); letter-spacing: 0.02em;
}
.reader-stat-value { color: var(--color-text-2); font-weight: 600; }

/* ── Story text ──────────────────────────────── */
.reader-body {
  font-family: var(--font-family-serif);
  font-size: 1.2rem; font-weight: 400;
  color: var(--color-text-1);
  line-height: 1.85;
  letter-spacing: 0.01em;
  padding-bottom: 4rem;
}
.reader-body p { margin-bottom: 1.4em; text-indent: 0; }
.reader-body p:first-child { font-size: 1.25rem; }
.reader-body p:first-child::first-letter {
  font-size: 3.2em;
  float: left;
  line-height: 0.8;
  margin: 0.06em 0.12em 0 0;
  color: var(--color-accent);
  font-weight: 700;
  font-family: var(--font-family-serif);
}
.reader-body hr {
  border: none;
  text-align: center;
  margin: 2.5rem 0;
  color: var(--color-text-3);
  font-size: 1rem;
  letter-spacing: 0.5em;
}
.reader-body hr::after { content: '\2022  \2022  \2022'; }

/* ── Series nav ──────────────────────────────── */
.reader-series-nav {
  border-top: 1px solid var(--color-border);
  padding: 1.5rem 0 0;
  margin-top: 1rem;
}
.reader-series-title {
  font-family: var(--font-family-serif);
  font-size: 1rem; font-weight: 500;
  color: var(--color-text-2);
  margin-bottom: 0.6rem;
  letter-spacing: 0.03em;
  text-align: center;
}
.reader-series-list {
  list-style: none;
  display: flex; flex-direction: column; gap: 0.4rem;
}
.series-part {
  display: flex; align-items: center; gap: 0.6rem;
  padding: 0.55rem 0.85rem;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  text-decoration: none; color: var(--color-text-2);
  font-family: var(--font-family-sans);
  font-size: 0.82rem; transition: all 0.2s;
}
.series-part:hover {
  border-color: var(--color-border-hover);
  background: var(--color-surface-hover);
}
.series-part.current {
  border-color: rgba(160,32,32,0.3);
  background: var(--color-accent-dim);
}
.series-part-num {
  font-weight: 600; color: var(--color-text-3);
  min-width: 1.5rem; text-align: center;
}

/* ── Footer ──────────────────────────────────── */
.reader-footer {
  border-top: 1px solid var(--color-border);
  padding: 2rem 0;
  display: flex; justify-content: center;
  gap: 1rem; flex-wrap: wrap;
}
.btn-secondary {
  padding: 0.5rem 1.1rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-2);
  font-family: var(--font-family-sans);
  font-size: 0.8rem;
  text-decoration: none;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-secondary:hover {
  border-color: var(--color-border-hover);
  background: var(--color-surface-hover);
  color: var(--color-text-1);
}
</style>
