<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { settingsApi } from '@/api/client'
import { useNotificationStore } from '@/stores/notifications'
import type { VoiceEntry } from '@/types'

const notify = useNotificationStore()

// ── Tab state ─────────────────────────────────────────────
const activeTab = ref<'reddit' | 'voices'>('reddit')

// ── Reddit tab state ──────────────────────────────────────
const ttlOptions = [
  { value: 3600, label: '1 hour' },
  { value: 21600, label: '6 hours' },
  { value: 43200, label: '12 hours' },
  { value: 86400, label: '1 day' },
  { value: 604800, label: '1 week' },
  { value: 2592000, label: '1 month' },
]

const currentTtl = ref(604800)
const savingTtl = ref(false)
const uploadTimeframe = ref('alltime')
const uploadFile = ref<File | null>(null)
const uploading = ref(false)

// ── Voice Library tab state ───────────────────────────────
const voicePool = ref<(VoiceEntry & { notes?: string })[]>([])
const voiceFilter = ref<'all' | 'male' | 'female'>('all')
const voiceNotes = ref<Record<string, string>>({})
const previewPlayingId = ref<string | null>(null)
const noteSaveTimers: Record<string, ReturnType<typeof setTimeout>> = {}
let previewAudio: HTMLAudioElement | null = null

const filteredVoices = computed(() => {
  if (voiceFilter.value === 'all') return voicePool.value
  return voicePool.value.filter((v) => v.gender === voiceFilter.value)
})

onMounted(async () => {
  previewAudio = new Audio()
  previewAudio.addEventListener('ended', () => {
    previewPlayingId.value = null
  })

  // Load settings + voices in parallel
  try {
    const [settings, voices, notes] = await Promise.all([
      settingsApi.get().catch(() => ({} as Record<string, string>)),
      settingsApi.voices().catch(() => [] as VoiceEntry[]),
      settingsApi.voiceNotes().catch(() => ({} as Record<string, string>)),
    ])

    if (settings.reddit_cache_ttl) {
      currentTtl.value = parseInt(settings.reddit_cache_ttl) || 604800
    }

    voicePool.value = voices
    voiceNotes.value = notes
  } catch {
    notify.show('Failed to load settings', 'error')
  }
})

onBeforeUnmount(() => {
  if (previewAudio) {
    previewAudio.pause()
    previewAudio.src = ''
    previewAudio = null
  }
  for (const timer of Object.values(noteSaveTimers)) {
    clearTimeout(timer)
  }
})

// ── Reddit: Save TTL ──────────────────────────────────────
async function saveTtl() {
  savingTtl.value = true
  try {
    await settingsApi.update({ reddit_cache_ttl: currentTtl.value })
    notify.show('Refresh interval saved')
  } catch {
    notify.show('Failed to save setting', 'error')
  } finally {
    savingTtl.value = false
  }
}

// ── Reddit: Upload JSON ───────────────────────────────────
function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  uploadFile.value = input.files?.[0] || null
}

async function uploadJson() {
  if (!uploadFile.value) {
    notify.show('Please select a JSON file', 'warn')
    return
  }
  uploading.value = true
  try {
    const result = await settingsApi.uploadRedditCache(uploadTimeframe.value, uploadFile.value)
    notify.show(`Uploaded ${result.posts_count} posts for ${result.timeframe}`)
    uploadFile.value = null
  } catch {
    notify.show('Upload failed', 'error')
  } finally {
    uploading.value = false
  }
}

// ── Voice: Preview ────────────────────────────────────────
function togglePreview(voiceId: string) {
  if (!previewAudio) return

  if (previewPlayingId.value === voiceId) {
    previewAudio.pause()
    previewAudio.currentTime = 0
    previewPlayingId.value = null
    return
  }

  previewAudio.src = settingsApi.voicePreviewUrl(voiceId)
  previewAudio.play().catch(() => {
    notify.show('Failed to play preview', 'error')
  })
  previewPlayingId.value = voiceId
}

// ── Voice: Notes (debounced save) ─────────────────────────
function onNoteInput(voiceId: string, value: string) {
  voiceNotes.value[voiceId] = value

  if (noteSaveTimers[voiceId]) clearTimeout(noteSaveTimers[voiceId])
  noteSaveTimers[voiceId] = setTimeout(() => saveNote(voiceId), 800)
}

async function saveNote(voiceId: string) {
  try {
    await settingsApi.updateVoiceNotes({ [voiceId]: voiceNotes.value[voiceId] || '' })
  } catch {
    notify.show('Failed to save note', 'error')
  }
}

function getNote(voiceId: string): string {
  return voiceNotes.value[voiceId] || ''
}
</script>

<template>
  <div class="page-container">
    <router-link to="/" class="back-link">&larr; All stories</router-link>

    <div class="header">
      <h1>Settings</h1>
      <p>Configure your production environment</p>
    </div>

    <!-- Tab nav -->
    <div class="tab-nav">
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'reddit' }"
        @click="activeTab = 'reddit'"
      >Reddit</button>
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'voices' }"
        @click="activeTab = 'voices'"
      >Voice Library</button>
    </div>

    <!-- Reddit Tab -->
    <div v-show="activeTab === 'reddit'" class="tab-panel">
      <div class="settings-section">
        <h2>Reddit Refresh Interval</h2>
        <p>How often to re-fetch top stories from Reddit. Cached data is served between refreshes.</p>
        <div class="setting-row">
          <label>Refresh every</label>
          <select v-model.number="currentTtl" class="settings-select">
            <option v-for="opt in ttlOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
          </select>
          <button class="save-btn" :disabled="savingTtl" @click="saveTtl">
            {{ savingTtl ? 'Saving...' : 'Save' }}
          </button>
        </div>
      </div>

      <div class="settings-section">
        <h2>Manual Reddit Data Upload</h2>
        <p>
          If Reddit is unreachable, you can manually download the JSON and upload it here.
          Visit <code>https://www.reddit.com/r/nosleep/top.json?t=all&amp;limit=50</code> in your browser,
          save the page as a .json file, then upload it below.
        </p>
        <div class="upload-area">
          <div class="setting-row">
            <label>Timeframe</label>
            <select v-model="uploadTimeframe" class="settings-select">
              <option value="alltime">All Time</option>
              <option value="year">This Year</option>
              <option value="month">This Month</option>
              <option value="week">This Week</option>
              <option value="today">Today</option>
            </select>
          </div>
          <div class="upload-row">
            <input type="file" accept=".json,application/json" @change="onFileChange" />
            <button class="upload-btn" :disabled="uploading" @click="uploadJson">
              {{ uploading ? 'Uploading...' : 'Upload' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Voice Library Tab -->
    <div v-show="activeTab === 'voices'" class="tab-panel">
      <div class="voice-filter-row">
        <button
          v-for="f in (['all', 'male', 'female'] as const)"
          :key="f"
          class="filter-btn"
          :class="{ active: voiceFilter === f }"
          @click="voiceFilter = f"
        >{{ f === 'all' ? 'All' : f.charAt(0).toUpperCase() + f.slice(1) }}</button>
      </div>

      <div class="voice-list">
        <div v-for="voice in filteredVoices" :key="voice.voice_id" class="voice-card">
          <div class="voice-card-header">
            <span class="voice-name">{{ voice.name }}</span>
            <span class="voice-badge gender" :class="voice.gender">{{ voice.gender }}</span>
            <span class="voice-badge age">{{ voice.age }}</span>
          </div>
          <div class="voice-archetypes">{{ voice.archetypes.join(', ') }}</div>
          <div class="voice-actions">
            <button
              class="preview-btn"
              :class="{ playing: previewPlayingId === voice.voice_id }"
              @click="togglePreview(voice.voice_id)"
            >
              {{ previewPlayingId === voice.voice_id ? '&#9632; Stop' : '&#9654; Preview' }}
            </button>
          </div>
          <div class="voice-notes">
            <textarea
              class="notes-textarea"
              :value="getNote(voice.voice_id)"
              placeholder="Add notes about this voice..."
              rows="2"
              @input="onNoteInput(voice.voice_id, ($event.target as HTMLTextAreaElement).value)"
            ></textarea>
          </div>
        </div>
      </div>

      <div v-if="filteredVoices.length === 0" class="empty-state">
        <p>No voices found.</p>
      </div>
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

.page-container { max-width: 720px; margin: 0 auto; padding: 1.25rem; }

.header { padding: 1.25rem 0 1.5rem; }
.header h1 {
  font-family: var(--font-family-serif);
  font-size: 1.5rem; font-weight: 500;
  color: var(--color-text-1);
}
.header p {
  font-size: 0.8rem; color: var(--color-text-3);
  margin-top: 0.25rem;
}

/* ── Tabs ────────────────────────────────────── */
.tab-nav {
  display: flex; gap: 0;
  border-bottom: 1px solid var(--color-border);
  margin-bottom: 1.5rem;
}
.tab-btn {
  padding: 0.75rem 1.25rem;
  background: none; border: none;
  color: var(--color-text-3);
  font-family: var(--font-family-serif);
  font-size: 0.9rem; font-weight: 500;
  cursor: pointer; transition: all 0.2s;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
}
.tab-btn:hover { color: var(--color-text-2); }
.tab-btn.active {
  color: var(--color-text-1);
  border-bottom-color: var(--color-accent);
}

/* ── Settings sections ───────────────────────── */
.settings-section {
  margin-bottom: 2rem;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid var(--color-border);
}
.settings-section:last-child { border-bottom: none; }
.settings-section h2 {
  font-family: var(--font-family-serif);
  font-size: 1.1rem; font-weight: 500;
  color: var(--color-text-1);
  margin-bottom: 0.4rem;
}
.settings-section p {
  font-size: 0.82rem; color: var(--color-text-3);
  margin-bottom: 1rem; line-height: 1.5;
}
.settings-section code {
  font-size: 0.75rem;
  background: var(--color-surface);
  padding: 0.15rem 0.4rem;
  border-radius: 3px;
  color: var(--color-text-2);
  word-break: break-all;
}

.setting-row {
  display: flex; align-items: center;
  gap: 0.75rem; flex-wrap: wrap;
}
.setting-row label {
  font-size: 0.82rem; color: var(--color-text-2);
  white-space: nowrap;
}
.settings-select {
  padding: 0.45rem 0.75rem;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text-1);
  font-family: var(--font-family-sans);
  font-size: 0.82rem;
  color-scheme: dark;
  cursor: pointer;
}
.save-btn {
  padding: 0.45rem 1rem;
  background: var(--color-accent);
  border: none; border-radius: var(--radius-sm);
  color: #fff; font-size: 0.82rem;
  font-weight: 600; cursor: pointer;
  transition: all 0.2s;
}
.save-btn:hover { background: var(--color-accent-hover); }
.save-btn:disabled {
  background: rgba(255,255,255,0.06);
  color: var(--color-text-3);
  cursor: not-allowed;
}

.upload-area {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 1rem;
}
.upload-row {
  display: flex; align-items: center;
  gap: 0.75rem; margin-top: 0.75rem; flex-wrap: wrap;
}
.upload-row input[type="file"] {
  font-size: 0.8rem; color: var(--color-text-2);
}
.upload-btn {
  padding: 0.45rem 1rem;
  background: var(--color-surface-hover);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text-1);
  font-size: 0.82rem;
  font-weight: 500; cursor: pointer;
  transition: all 0.2s;
}
.upload-btn:hover {
  background: var(--color-surface-active);
  border-color: var(--color-border-hover);
}
.upload-btn:disabled {
  opacity: 0.5; cursor: not-allowed;
}

/* ── Voice Library ───────────────────────────── */
.voice-filter-row {
  display: flex; gap: 0.5rem; margin-bottom: 1.25rem;
}
.filter-btn {
  padding: 0.4rem 1rem;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 20px;
  color: var(--color-text-3);
  font-size: 0.78rem; font-weight: 500;
  cursor: pointer; transition: all 0.2s;
}
.filter-btn:hover {
  border-color: var(--color-border-hover);
  color: var(--color-text-2);
}
.filter-btn.active {
  background: var(--color-accent-dim);
  border-color: rgba(160,32,32,0.3);
  color: var(--color-accent);
}

.voice-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 0.75rem;
}
.voice-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 1rem;
  transition: border-color 0.2s;
}
.voice-card:hover { border-color: var(--color-border-hover); }
.voice-card-header {
  display: flex; align-items: center; gap: 0.5rem;
  margin-bottom: 0.4rem;
}
.voice-name {
  font-family: var(--font-family-serif);
  font-size: 1rem; font-weight: 600;
  color: var(--color-text-1);
}
.voice-badge {
  font-size: 0.6rem; font-weight: 600;
  text-transform: uppercase;
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  letter-spacing: 0.04em;
}
.voice-badge.gender.male { background: var(--color-info-dim); color: var(--color-info); }
.voice-badge.gender.female { background: rgba(184,72,184,0.12); color: #b848b8; }
.voice-badge.age { background: var(--color-surface-active); color: var(--color-text-3); }

.voice-archetypes {
  font-size: 0.78rem; color: var(--color-text-3);
  font-style: italic; margin-bottom: 0.6rem;
}

.voice-actions { margin-bottom: 0.5rem; }
.preview-btn {
  padding: 0.35rem 0.8rem;
  background: var(--color-surface-hover);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text-2);
  font-size: 0.75rem; cursor: pointer;
  transition: all 0.2s;
}
.preview-btn:hover {
  border-color: var(--color-border-hover);
  color: var(--color-text-1);
}
.preview-btn.playing {
  background: var(--color-accent-dim);
  border-color: rgba(160,32,32,0.3);
  color: var(--color-accent);
}

.voice-notes { margin-top: 0.25rem; }
.notes-textarea {
  width: 100%;
  padding: 0.4rem 0.6rem;
  background: rgba(0,0,0,0.2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text-1);
  font-family: var(--font-family-sans);
  font-size: 0.78rem;
  resize: vertical;
  outline: none;
  transition: border-color 0.2s;
}
.notes-textarea:focus { border-color: var(--color-border-focus); }
.notes-textarea::placeholder { color: var(--color-text-3); }

.empty-state { text-align: center; padding: 3rem 1rem; color: var(--color-text-3); }
</style>
