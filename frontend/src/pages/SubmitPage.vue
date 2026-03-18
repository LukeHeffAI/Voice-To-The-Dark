<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import type { TopNosleepPost } from '../api/types'
import * as storiesApi from '../api/stories'
import { useNotificationStore } from '../stores/notifications'

const router = useRouter()
const notifications = useNotificationStore()

// ── Browse top stories ──────────────────────────────
const timeframe = ref('alltime')
const topStories = ref<TopNosleepPost[]>([])
const browseLoading = ref(false)

async function loadTopStories() {
  browseLoading.value = true
  try {
    topStories.value = await storiesApi.topNosleep(timeframe.value)
  } catch {
    notifications.show('Failed to load top stories', 'error')
  } finally {
    browseLoading.value = false
  }
}

watch(timeframe, loadTopStories, { immediate: true })

// ── Manual entry panel ──────────────────────────────
const panelOpen = ref(false)
const manualUrl = ref('')
const manualTitle = ref('')
const manualAuthor = ref('')
const manualText = ref('')
const fieldsLocked = ref(false)
const submitting = ref(false)
const fetchingPreview = ref(false)

let fetchController: AbortController | null = null
let fetchDebounce: ReturnType<typeof setTimeout> | null = null

function openPanel(post?: TopNosleepPost) {
  panelOpen.value = true
  if (post) {
    manualUrl.value = post.url
    manualTitle.value = post.title
    manualAuthor.value = post.author
    manualText.value = ''
    fieldsLocked.value = false
    autoFetch(post.url)
  }
}

function closePanel() {
  panelOpen.value = false
  clearForm()
}

function clearForm() {
  manualUrl.value = ''
  manualTitle.value = ''
  manualAuthor.value = ''
  manualText.value = ''
  fieldsLocked.value = false
  abortFetch()
}

function abortFetch() {
  if (fetchController) {
    fetchController.abort()
    fetchController = null
  }
  if (fetchDebounce) {
    clearTimeout(fetchDebounce)
    fetchDebounce = null
  }
}

function autoFetch(url: string) {
  abortFetch()
  if (!url.trim()) return

  fetchDebounce = setTimeout(async () => {
    fetchingPreview.value = true
    fetchController = new AbortController()
    try {
      const preview = await storiesApi.fetchPreview(url, fetchController.signal)
      manualTitle.value = preview.title
      manualAuthor.value = preview.author
      manualText.value = preview.text
      fieldsLocked.value = true
    } catch {
      // Aborted or failed — user can fill manually
    } finally {
      fetchingPreview.value = false
    }
  }, 600)
}

watch(manualUrl, (url) => {
  if (url && !fieldsLocked.value) {
    autoFetch(url)
  }
})

function clearUrl() {
  manualUrl.value = ''
  fieldsLocked.value = false
  manualTitle.value = ''
  manualAuthor.value = ''
  manualText.value = ''
  abortFetch()
}

async function submitManual() {
  if (!manualTitle.value && !manualText.value && !manualUrl.value) {
    notifications.show('Please provide at least a title or text', 'error')
    return
  }
  submitting.value = true
  try {
    const story = await storiesApi.submitManual({
      title: manualTitle.value || undefined,
      author: manualAuthor.value || undefined,
      text_content: manualText.value || undefined,
      reddit_url: manualUrl.value || undefined,
    })
    notifications.show('Story submitted!', 'success')
    router.push({ name: 'story-detail', params: { id: story.id } })
  } catch (e) {
    notifications.show(e instanceof Error ? e.message : 'Submit failed', 'error')
  } finally {
    submitting.value = false
  }
}

onUnmounted(abortFetch)

const timeframes = [
  { value: 'alltime', label: 'All Time' },
  { value: 'year', label: 'Year' },
  { value: 'month', label: 'Month' },
  { value: 'week', label: 'Week' },
]
</script>

<template>
  <div class="submit-layout">
    <!-- Left: Browse -->
    <div class="browse-section">
      <h1 class="page-title">Submit Story</h1>

      <div class="timeframe-tabs">
        <button
          v-for="tf in timeframes"
          :key="tf.value"
          class="tf-tab"
          :class="{ active: timeframe === tf.value }"
          @click="timeframe = tf.value"
        >
          {{ tf.label }}
        </button>
        <button class="tf-tab manual-btn" @click="openPanel()">+ Manual Entry</button>
      </div>

      <div v-if="browseLoading" class="loading">Loading top stories...</div>
      <div v-else class="top-list">
        <div
          v-for="post in topStories"
          :key="post.url"
          class="top-item"
          :class="{ submitted: post.already_submitted }"
          @click="openPanel(post)"
        >
          <div class="top-score">{{ post.score }}</div>
          <div class="top-info">
            <div class="top-title">{{ post.title }}</div>
            <div class="top-meta">
              u/{{ post.author }}
              <span v-if="post.is_series" class="series-badge">Series</span>
            </div>
          </div>
          <span v-if="post.already_submitted" class="submitted-badge">✓</span>
        </div>
      </div>
    </div>

    <!-- Right: Manual entry panel (slide-out) -->
    <div v-if="panelOpen" class="panel-backdrop" @click="closePanel" />
    <div class="entry-panel" :class="{ open: panelOpen }">
      <div class="panel-header">
        <h2 class="panel-title">Add Story</h2>
        <button class="panel-close" @click="closePanel">✕</button>
      </div>

      <div class="panel-body">
        <div class="field">
          <label class="field-label">Reddit URL (optional)</label>
          <div class="url-row">
            <input
              v-model="manualUrl"
              class="field-input"
              placeholder="https://reddit.com/r/nosleep/..."
              :disabled="fieldsLocked"
            />
            <button v-if="fieldsLocked" class="clear-btn" @click="clearUrl">Clear</button>
          </div>
          <span v-if="fetchingPreview" class="fetch-status">Fetching...</span>
        </div>

        <div class="field">
          <label class="field-label">Title</label>
          <input
            v-model="manualTitle"
            class="field-input"
            placeholder="Story title"
            :readonly="fieldsLocked"
          />
        </div>

        <div class="field">
          <label class="field-label">Author</label>
          <input
            v-model="manualAuthor"
            class="field-input"
            placeholder="Author"
            :readonly="fieldsLocked"
          />
        </div>

        <div class="field">
          <label class="field-label">Text</label>
          <textarea
            v-model="manualText"
            class="field-textarea"
            placeholder="Paste story text..."
            rows="12"
            :readonly="fieldsLocked"
          />
        </div>

        <button class="submit-btn" :disabled="submitting" @click="submitManual">
          {{ submitting ? 'Submitting...' : 'Submit' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.submit-layout {
  position: relative;
}

.page-title {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 1.6rem;
  font-weight: 400;
  color: rgba(255, 255, 255, 0.9);
  margin-bottom: 1rem;
}

.timeframe-tabs {
  display: flex;
  gap: 0.4rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}
.tf-tab {
  padding: 0.4rem 0.75rem;
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(255, 255, 255, 0.025);
  color: #8a8a8a;
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.15s;
}
.tf-tab:hover {
  background: rgba(255, 255, 255, 0.045);
}
.tf-tab.active {
  background: rgba(160, 32, 32, 0.12);
  border-color: rgba(160, 32, 32, 0.25);
  color: var(--color-accent);
}
.manual-btn {
  margin-left: auto;
}

.loading {
  text-align: center;
  padding: 2rem;
  color: #555;
  font-size: 0.85rem;
}

.top-list {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.top-item {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.55rem 0.7rem;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
}
.top-item:hover {
  background: rgba(255, 255, 255, 0.03);
}
.top-item.submitted {
  opacity: 0.5;
}

.top-score {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--color-accent);
  min-width: 35px;
  text-align: right;
}

.top-info {
  flex: 1;
  min-width: 0;
}
.top-title {
  font-size: 0.82rem;
  color: #e8e6e3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.top-meta {
  font-size: 0.7rem;
  color: #555;
}
.series-badge {
  display: inline-block;
  padding: 0.05rem 0.35rem;
  border-radius: 10px;
  background: rgba(104, 104, 184, 0.12);
  color: var(--color-info);
  font-size: 0.6rem;
  font-weight: 600;
  margin-left: 0.3rem;
  text-transform: uppercase;
}
.submitted-badge {
  color: var(--color-success);
  font-size: 0.8rem;
}

/* Entry panel */
.panel-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 200;
}

.entry-panel {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  width: 460px;
  max-width: 92vw;
  background: #0a0a0a;
  border-left: 1px solid rgba(255, 255, 255, 0.08);
  z-index: 201;
  transform: translateX(100%);
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  display: flex;
  flex-direction: column;
}
.entry-panel.open {
  transform: translateX(0);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
}
.panel-title {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 1.1rem;
  font-weight: 500;
  color: #e8e6e3;
}
.panel-close {
  background: none;
  border: none;
  color: #555;
  font-size: 1.1rem;
  cursor: pointer;
  padding: 0.3rem;
}
.panel-close:hover {
  color: #e8e6e3;
}

.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 1rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.field-label {
  display: block;
  font-size: 0.72rem;
  color: #8a8a8a;
  margin-bottom: 0.3rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.field-input {
  width: 100%;
  padding: 0.55rem 0.75rem;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 8px;
  color: #e8e6e3;
  font-size: 0.85rem;
  font-family: inherit;
}
.field-input:focus {
  outline: none;
  border-color: rgba(160, 32, 32, 0.4);
}
.field-input:read-only {
  opacity: 0.7;
  cursor: not-allowed;
}
.field-textarea {
  width: 100%;
  padding: 0.55rem 0.75rem;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 8px;
  color: #e8e6e3;
  font-size: 0.85rem;
  font-family: inherit;
  resize: vertical;
}
.field-textarea:focus {
  outline: none;
  border-color: rgba(160, 32, 32, 0.4);
}

.url-row {
  display: flex;
  gap: 0.3rem;
}
.url-row .field-input {
  flex: 1;
}
.clear-btn {
  padding: 0.4rem 0.6rem;
  background: none;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  color: #8a8a8a;
  font-size: 0.75rem;
  cursor: pointer;
}
.fetch-status {
  font-size: 0.7rem;
  color: #555;
  margin-top: 0.2rem;
}

.submit-btn {
  padding: 0.65rem;
  background: var(--color-accent);
  border: none;
  border-radius: 8px;
  color: white;
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
  margin-top: 0.5rem;
}
.submit-btn:hover:not(:disabled) {
  background: var(--color-accent-hover);
}
.submit-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
