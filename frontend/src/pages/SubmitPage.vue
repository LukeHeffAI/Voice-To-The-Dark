<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { storiesApi } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useNotificationStore } from '@/stores/notifications'
import { ApiError } from '@/api/client'
import type { TopPost } from '@/types'

const router = useRouter()
const auth = useAuthStore()
const notify = useNotificationStore()

// ── Browse top stories ──────────────────────────────
const timeframes = [
  { key: 'alltime', label: 'All Time' },
  { key: 'year', label: 'This Year' },
  { key: 'month', label: 'This Month' },
  { key: 'week', label: 'This Week' },
]
const activeFilter = ref('alltime')
const topStories = ref<TopPost[]>([])
const topLoading = ref(true)
const topError = ref('')
const submittingUrl = ref<string | null>(null)
const storyCache: Record<string, TopPost[]> = {}

async function loadTopStories(timeframe: string) {
  activeFilter.value = timeframe
  if (storyCache[timeframe]) {
    topStories.value = storyCache[timeframe]
    topLoading.value = false
    return
  }
  topLoading.value = true
  topError.value = ''
  try {
    const data = await storiesApi.topNosleep(timeframe)
    storyCache[timeframe] = data
    topStories.value = data
  } catch {
    topError.value = 'Reddit browsing unavailable — use Manual Entry to add stories directly.'
  } finally {
    topLoading.value = false
  }
}

async function submitTopStory(story: TopPost) {
  if (!auth.isLoggedIn) { router.push('/login?redirect=/submit'); return }
  submittingUrl.value = story.url
  try {
    const data = await storiesApi.submitManual({ reddit_url: story.url, title: story.title, author: story.author })
    router.push(`/story/${data.id}`)
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) { router.push('/login?redirect=/submit'); return }
    const body = (e instanceof ApiError ? e.body : null) as { detail?: string } | null
    notify.show(body?.detail || 'Failed to submit story', 'error')
    submittingUrl.value = null
  }
}

function formatScore(score?: number) {
  if (!score) return ''
  return score >= 1000 ? (score / 1000).toFixed(1) + 'k' : score.toString()
}

// ── Manual entry panel ──────────────────────────────
const panelOpen = ref(false)
const manualUrl = ref('')
const manualTitle = ref('')
const manualText = ref('')
const urlStatus = ref<{ text: string; type: string }>({ text: '', type: '' })
const fieldsLocked = ref(false)
const manualSubmitting = ref(false)
const manualError = ref('')

let fetchTimer: ReturnType<typeof setTimeout> | null = null
let fetchController: AbortController | null = null

function onUrlInput() {
  if (fetchTimer) clearTimeout(fetchTimer)
  const url = manualUrl.value.trim()
  if (!url) { unlockFields(); return }
  if (!url.match(/reddit\.com\/r\/nosleep\/comments\//i)) {
    urlStatus.value = { text: '', type: '' }
    return
  }
  fetchTimer = setTimeout(() => fetchPreview(url), 600)
}

async function fetchPreview(url: string) {
  if (fetchController) fetchController.abort()
  fetchController = new AbortController()
  urlStatus.value = { text: 'Fetching story details...', type: 'fetching' }
  try {
    const data = await storiesApi.fetchPreview(url)
    if (manualUrl.value.trim() !== url) return
    manualTitle.value = data.title || ''
    manualText.value = data.text || ''
    fieldsLocked.value = true
    urlStatus.value = { text: 'Story details loaded.', type: 'success' }
  } catch (e) {
    if ((e as Error).name === 'AbortError') return
    const body = (e instanceof ApiError ? e.body : null) as { detail?: string } | null
    urlStatus.value = { text: body?.detail || 'Could not fetch story.', type: 'error' }
  }
}

function unlockFields() {
  const wasLocked = fieldsLocked.value
  fieldsLocked.value = false
  urlStatus.value = { text: '', type: '' }
  if (wasLocked) { manualTitle.value = ''; manualText.value = '' }
}

async function submitManual() {
  const title = manualTitle.value.trim()
  const text = manualText.value.trim()
  const url = manualUrl.value.trim() || undefined
  if (!url && !title && !text) { manualError.value = 'Enter a URL, or provide a title and story text.'; return }
  if (!url && (!title || !text)) { manualError.value = 'Without a URL, both title and story text are required.'; return }
  manualSubmitting.value = true
  manualError.value = ''
  try {
    const data = await storiesApi.submitManual({
      reddit_url: url,
      title: title || undefined,
      text_content: text || undefined,
    })
    router.push(`/story/${data.id}`)
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) { router.push('/login?redirect=/submit'); return }
    const body = (e instanceof ApiError ? e.body : null) as { detail?: string } | null
    manualError.value = body?.detail || 'Submission failed.'
    manualSubmitting.value = false
  }
}

function closePanelOnEsc(e: KeyboardEvent) {
  if (e.key === 'Escape' && panelOpen.value) panelOpen.value = false
}

onMounted(() => {
  loadTopStories('alltime')
  document.addEventListener('keydown', closePanelOnEsc)
})
onUnmounted(() => document.removeEventListener('keydown', closePanelOnEsc))
</script>

<template>
  <div class="page-container">
    <router-link to="/" class="back-link">&larr; All stories</router-link>

    <div class="header">
      <h1>Submit a Story</h1>
      <p>Pick from the best of r/nosleep</p>
    </div>

    <!-- Login prompt -->
    <div v-if="!auth.isLoggedIn" class="login-prompt">
      <p>Sign in to submit stories and generate narrations</p>
      <router-link to="/login?redirect=/submit" class="btn-primary">Sign In</router-link>
    </div>

    <!-- Browse section -->
    <div class="browse-section">
      <div class="browse-header">
        <h2>Best of r/nosleep</h2>
        <button v-if="auth.isLoggedIn" class="manual-btn" @click="panelOpen = true">+ Manual Entry</button>
      </div>
      <p class="subtitle">Tap a story to begin</p>

      <div class="filter-bar">
        <button
          v-for="tf in timeframes"
          :key="tf.key"
          class="filter-btn"
          :class="{ active: activeFilter === tf.key }"
          @click="loadTopStories(tf.key)"
        >
          {{ tf.label }}
        </button>
      </div>

      <!-- Loading / error -->
      <div v-if="topLoading" class="loading-state">
        <span class="spinner"></span> Loading top stories...
      </div>
      <div v-else-if="topError" class="text-text-3 text-center py-8 text-sm">{{ topError }}</div>

      <!-- Top stories list -->
      <ul v-else class="top-list">
        <li v-if="!topStories.length" class="text-text-3 text-center py-4 text-sm">No stories found for this timeframe.</li>
        <li
          v-for="story in topStories"
          :key="story.url"
          class="top-item"
          :class="{ submitting: submittingUrl === story.url }"
          @click="submitTopStory(story)"
        >
          <div class="top-info">
            <div class="top-title">{{ story.title }}</div>
            <div class="top-meta">
              <span v-if="story.author" class="top-author">u/{{ story.author }}</span>
            </div>
          </div>
          <div class="top-score">
            <span v-if="submittingUrl === story.url" class="spinner" style="margin:0"></span>
            <template v-else>{{ formatScore(story.score) }} pts</template>
          </div>
        </li>
      </ul>
    </div>

    <!-- Manual entry panel overlay -->
    <Teleport to="body">
      <div class="popout-overlay" :class="{ open: panelOpen }" @click.self="panelOpen = false">
        <div class="popout-panel" @click.stop>
          <div class="popout-header">
            <h3>Manual Entry</h3>
            <button class="popout-close" @click="panelOpen = false">&times;</button>
          </div>
          <div class="popout-body">
            <p class="hint">All fields are optional. Paste a Reddit URL to auto-fill the title and text.</p>
            <div class="manual-form">
              <div class="field-group">
                <label>Reddit URL</label>
                <input
                  v-model="manualUrl"
                  type="text"
                  class="form-input"
                  placeholder="https://reddit.com/r/nosleep/comments/..."
                  @input="onUrlInput"
                />
                <div v-if="urlStatus.text" class="url-status" :class="urlStatus.type">{{ urlStatus.text }}</div>
              </div>
              <div class="field-group">
                <label>Story Title</label>
                <input v-model="manualTitle" type="text" class="form-input" placeholder="e.g. I Found Something in My Basement" :readonly="fieldsLocked" />
              </div>
              <div class="field-group">
                <label>Story Text</label>
                <textarea v-model="manualText" class="form-input" style="min-height:180px;resize:vertical" placeholder="Paste the full story text here..." :readonly="fieldsLocked"></textarea>
              </div>
              <div v-if="manualError" class="py-2 px-3 rounded-[var(--radius-sm)] text-[0.82rem] bg-error-dim border border-error/20 text-[#e07070]">
                {{ manualError }}
              </div>
              <button class="btn-primary w-full" :disabled="manualSubmitting" @click="submitManual">
                <span v-if="manualSubmitting" class="spinner"></span>
                {{ manualSubmitting ? 'Submitting...' : 'Submit' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.back-link {
  display: inline-flex; align-items: center; gap: 0.4rem; color: var(--color-text-3);
  text-decoration: none; font-size: 0.8rem; padding: 0.5rem 0; transition: color 0.2s;
  letter-spacing: 0.03em; text-transform: uppercase;
}
.back-link:hover { color: var(--color-text-2); }
.header {
  text-align: center; padding: 2rem 0; border-bottom: 1px solid var(--color-border); margin-bottom: 1.75rem;
}
.header h1 {
  font-family: var(--font-family-serif); font-weight: 300; font-size: 1.8rem;
  letter-spacing: 0.12em; text-transform: uppercase; color: var(--color-text-1);
}
.header p {
  font-family: var(--font-family-serif); font-size: 0.95rem; font-weight: 300;
  font-style: italic; color: var(--color-text-3); margin-top: 0.4rem;
}
.login-prompt {
  text-align: center; padding: 1.75rem; background: var(--color-surface);
  border: 1px solid var(--color-border); border-radius: var(--radius-md); margin-bottom: 2rem;
}
.login-prompt p { color: var(--color-text-2); font-size: 0.88rem; margin-bottom: 0.85rem; }
.browse-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.35rem; }
.browse-header h2 {
  font-family: var(--font-family-serif); font-size: 1.1rem; font-weight: 500;
  color: var(--color-text-1); letter-spacing: 0.03em;
}
.subtitle { font-size: 0.78rem; color: var(--color-text-3); margin-bottom: 1rem; }
.manual-btn {
  padding: 0.42rem 0.9rem; border: 1px solid var(--color-border); border-radius: var(--radius-sm);
  background: transparent; color: var(--color-text-3); font-size: 0.78rem; font-weight: 500;
  cursor: pointer; transition: all 0.25s; letter-spacing: 0.02em; white-space: nowrap;
}
.manual-btn:hover { border-color: var(--color-border-hover); color: var(--color-text-2); background: var(--color-surface); }
.filter-bar { display: flex; gap: 0.4rem; margin-bottom: 1rem; flex-wrap: wrap; }
.filter-btn {
  padding: 0.38rem 0.8rem; border: 1px solid var(--color-border); border-radius: 20px;
  background: transparent; color: var(--color-text-3); font-size: 0.75rem; font-weight: 500;
  cursor: pointer; transition: all 0.25s; letter-spacing: 0.02em;
}
.filter-btn:hover { border-color: var(--color-border-hover); color: var(--color-text-2); }
.filter-btn.active { border-color: rgba(160,32,32,0.3); color: var(--color-accent); background: var(--color-accent-dim); }
.loading-state { text-align: center; padding: 2rem; color: var(--color-text-3); font-size: 0.85rem; }
.top-list { list-style: none; display: flex; flex-direction: column; gap: 0.5rem; }
.top-item {
  background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-sm);
  padding: 0.85rem 1rem; cursor: pointer; transition: all 0.2s; display: flex;
  justify-content: space-between; align-items: flex-start; gap: 0.75rem;
}
.top-item:hover { border-color: var(--color-border-hover); background: var(--color-surface-hover); }
.top-item.submitting { border-color: rgba(160,32,32,0.3); background: var(--color-accent-dim); pointer-events: none; }
.top-info { flex: 1; min-width: 0; }
.top-title { font-size: 0.88rem; color: var(--color-text-1); line-height: 1.35; }
.top-meta { font-size: 0.72rem; color: var(--color-text-3); margin-top: 0.25rem; display: flex; gap: 0.6rem; flex-wrap: wrap; }
.top-score { font-size: 0.72rem; color: var(--color-text-3); white-space: nowrap; padding-top: 0.1rem; font-variant-numeric: tabular-nums; }

/* Popout panel */
.popout-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 5000;
  opacity: 0; visibility: hidden; transition: opacity 0.25s, visibility 0.25s;
}
.popout-overlay.open { opacity: 1; visibility: visible; }
.popout-panel {
  position: fixed; top: 0; right: 0; bottom: 0; width: min(460px, 92vw);
  background: var(--color-bg); border-left: 1px solid var(--color-border); z-index: 5001;
  transform: translateX(100%); transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  display: flex; flex-direction: column; overflow-y: auto;
}
.popout-overlay.open .popout-panel { transform: translateX(0); }
.popout-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 1.25rem 1.5rem; border-bottom: 1px solid var(--color-border);
}
.popout-header h3 {
  font-family: var(--font-family-serif); font-size: 1.15rem; font-weight: 500;
  color: var(--color-text-1); letter-spacing: 0.03em;
}
.popout-close {
  width: 32px; height: 32px; border: 1px solid var(--color-border); border-radius: var(--radius-sm);
  background: transparent; color: var(--color-text-3); font-size: 1.1rem; cursor: pointer;
  display: flex; align-items: center; justify-content: center; transition: all 0.2s;
}
.popout-close:hover { border-color: var(--color-border-hover); color: var(--color-text-1); }
.popout-body { padding: 1.5rem; flex: 1; }
.hint { font-size: 0.73rem; color: var(--color-text-3); line-height: 1.5; margin-bottom: 1.25rem; font-style: italic; }
.manual-form { display: flex; flex-direction: column; gap: 1rem; }
.field-group { display: flex; flex-direction: column; gap: 0.3rem; }
.field-group label { font-size: 0.72rem; color: var(--color-text-3); text-transform: uppercase; letter-spacing: 0.06em; }
.url-status { font-size: 0.75rem; margin-top: 0.2rem; }
.url-status.fetching { color: var(--color-text-3); }
.url-status.success { color: var(--color-success); }
.url-status.error { color: #e07070; }
</style>
