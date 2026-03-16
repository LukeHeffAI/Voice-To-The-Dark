<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed } from 'vue'
import * as settingsApi from '../api/settings'
import { useNotificationStore } from '../stores/notifications'

const notifications = useNotificationStore()

// ── Tab state ──────────────────────────────────────
const activeTab = ref<'reddit' | 'voices'>('reddit')

// ── Reddit settings ────────────────────────────────
const cacheTtl = ref('3600')
const savingTtl = ref(false)

const ttlOptions = [
  { value: '3600', label: '1 Hour' },
  { value: '21600', label: '6 Hours' },
  { value: '86400', label: '1 Day' },
  { value: '604800', label: '1 Week' },
]

async function loadSettings() {
  try {
    const s = await settingsApi.getSettings()
    if (s.reddit_cache_ttl) cacheTtl.value = s.reddit_cache_ttl
  } catch {
    // Use defaults
  }
}

async function saveTtl() {
  savingTtl.value = true
  try {
    await settingsApi.updateSettings({ reddit_cache_ttl: cacheTtl.value })
    notifications.show('Settings saved', 'success')
  } catch {
    notifications.show('Failed to save settings', 'error')
  } finally {
    savingTtl.value = false
  }
}

// ── Upload ─────────────────────────────────────────
const uploadTimeframe = ref('alltime')
const uploading = ref(false)
const uploadFile = ref<File | null>(null)

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  uploadFile.value = input.files?.[0] || null
}

async function uploadJson() {
  if (!uploadFile.value) {
    notifications.show('Please select a .json file', 'error')
    return
  }
  uploading.value = true
  try {
    const result = await settingsApi.uploadRedditCache(uploadTimeframe.value, uploadFile.value)
    notifications.show(`Uploaded ${result.posts_count} posts for ${uploadTimeframe.value}`, 'success')
  } catch {
    notifications.show('Upload failed', 'error')
  } finally {
    uploading.value = false
  }
}

// ── Voice Library ──────────────────────────────────
interface VoiceInfo {
  voice_id: string
  name: string
  gender: string
  age: string
  role: string
  archetypes: string[]
  notes: string
  model: string
}

const voices = ref<VoiceInfo[]>([])
const filters = ref({ gender: '', role: '', age: '', archetype: '' })
const previewPlaying = ref<string | null>(null)
const previewLoading = ref<string | null>(null)
const noteSaved = ref<Record<string, boolean>>({})
let previewAudio: HTMLAudioElement | null = null
const noteSaveTimers: Record<string, ReturnType<typeof setTimeout>> = {}

const genderOptions = computed(() => {
  const set = new Set(voices.value.map((v) => v.gender))
  return Array.from(set).sort()
})

const roleOptions = computed(() => {
  const set = new Set(voices.value.map((v) => v.role))
  return Array.from(set).sort()
})

const ageOptions = computed(() => {
  const set = new Set(voices.value.map((v) => v.age))
  return Array.from(set).sort()
})

const archetypeOptions = computed(() => {
  const set = new Set(voices.value.flatMap((v) => v.archetypes))
  return Array.from(set).sort()
})

const filteredVoices = computed(() => {
  return voices.value.filter((v) => {
    if (filters.value.gender && v.gender !== filters.value.gender) return false
    if (filters.value.role && v.role !== filters.value.role) return false
    if (filters.value.age && v.age !== filters.value.age) return false
    if (filters.value.archetype && !v.archetypes.includes(filters.value.archetype)) return false
    return true
  })
})

async function loadVoices() {
  try {
    voices.value = await settingsApi.getVoicePool()
  } catch {
    // No voices available
  }
}

function togglePreview(voiceId: string) {
  if (!previewAudio) {
    previewAudio = new Audio()
  }

  // Stop if same voice playing
  if (previewPlaying.value === voiceId && !previewAudio.paused) {
    previewAudio.pause()
    previewAudio.currentTime = 0
    previewPlaying.value = null
    return
  }

  previewLoading.value = voiceId
  previewAudio.src = settingsApi.voicePreviewUrl(voiceId)
  previewAudio.load()

  previewAudio.oncanplaythrough = () => {
    previewAudio!.play()
    previewPlaying.value = voiceId
    previewLoading.value = null
  }

  previewAudio.onerror = () => {
    previewLoading.value = null
    previewPlaying.value = null
    notifications.show('Failed to load preview', 'error')
  }

  previewAudio.onended = () => {
    previewPlaying.value = null
  }
}

function onNoteInput(voiceId: string, value: string) {
  const voice = voices.value.find((v) => v.voice_id === voiceId)
  if (voice) voice.notes = value

  clearTimeout(noteSaveTimers[voiceId])
  noteSaveTimers[voiceId] = setTimeout(async () => {
    try {
      await settingsApi.updateVoiceNotes({ [voiceId]: value })
      noteSaved.value[voiceId] = true
      setTimeout(() => {
        noteSaved.value[voiceId] = false
      }, 1500)
    } catch {
      // Silent fail
    }
  }, 800)
}

onMounted(() => {
  loadSettings()
  loadVoices()
})

onUnmounted(() => {
  if (previewAudio) {
    previewAudio.pause()
    previewAudio = null
  }
  for (const timer of Object.values(noteSaveTimers)) {
    clearTimeout(timer)
  }
})
</script>

<template>
  <div class="page-container">
    <RouterLink to="/" class="back-link">&larr; All stories</RouterLink>

    <div class="header">
      <h1>Settings</h1>
      <p>Configure your production environment</p>
    </div>

    <div class="tab-nav">
      <button class="tab-btn" :class="{ active: activeTab === 'reddit' }" @click="activeTab = 'reddit'">
        Reddit
      </button>
      <button class="tab-btn" :class="{ active: activeTab === 'voices' }" @click="activeTab = 'voices'">
        Voice Library
      </button>
    </div>

    <!-- Reddit Tab -->
    <div v-if="activeTab === 'reddit'">
      <div class="settings-section">
        <h2>Reddit Refresh Interval</h2>
        <p>How often to re-fetch top stories from Reddit. Cached data is served between refreshes.</p>

        <div class="setting-row">
          <label>Refresh every</label>
          <select v-model="cacheTtl" class="select-input">
            <option v-for="opt in ttlOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
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

        <div class="setting-row">
          <label>Timeframe</label>
          <select v-model="uploadTimeframe" class="select-input">
            <option value="alltime">All Time</option>
            <option value="year">This Year</option>
            <option value="month">This Month</option>
            <option value="week">This Week</option>
            <option value="today">Today</option>
          </select>
        </div>
        <div class="upload-row">
          <input type="file" accept=".json,application/json" class="file-input" @change="onFileChange" />
          <button class="save-btn" :disabled="uploading" @click="uploadJson">
            {{ uploading ? 'Uploading...' : 'Upload' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Voice Library Tab -->
    <div v-if="activeTab === 'voices'">
      <div class="voice-filter-row">
        <div class="filter-group">
          <label class="filter-label">Gender</label>
          <select v-model="filters.gender" class="filter-select">
            <option value="">All</option>
            <option v-for="opt in genderOptions" :key="opt" :value="opt">{{ opt }}</option>
          </select>
        </div>
        <div class="filter-group">
          <label class="filter-label">Role</label>
          <select v-model="filters.role" class="filter-select">
            <option value="">All</option>
            <option v-for="opt in roleOptions" :key="opt" :value="opt">{{ opt }}</option>
          </select>
        </div>
        <div class="filter-group">
          <label class="filter-label">Age</label>
          <select v-model="filters.age" class="filter-select">
            <option value="">All</option>
            <option v-for="opt in ageOptions" :key="opt" :value="opt">{{ opt }}</option>
          </select>
        </div>
        <div class="filter-group">
          <label class="filter-label">Archetype</label>
          <select v-model="filters.archetype" class="filter-select">
            <option value="">All</option>
            <option v-for="opt in archetypeOptions" :key="opt" :value="opt">{{ opt }}</option>
          </select>
        </div>
      </div>
      <div class="voice-filter-count">{{ filteredVoices.length }} of {{ voices.length }} voices</div>

      <div v-if="filteredVoices.length === 0" class="empty">No voices match current filters</div>

      <div v-for="voice in filteredVoices" :key="voice.voice_id" class="voice-card">
        <div class="voice-card-header">
          <span class="voice-name">{{ voice.name }}</span>
          <span class="voice-badge" :class="voice.gender">{{ voice.gender }}</span>
          <span v-if="voice.age" class="voice-badge">{{ voice.age }}</span>
          <span class="voice-badge" :class="voice.role">{{ voice.role }}</span>
        </div>
        <div class="voice-archetypes">{{ voice.archetypes.join(', ') }}</div>

        <div class="voice-preview-row">
          <button
            class="preview-btn"
            :class="{ loading: previewLoading === voice.voice_id }"
            @click="togglePreview(voice.voice_id)"
          >
            <span v-if="previewPlaying === voice.voice_id" class="icon">&#9724;</span>
            <span v-else-if="previewLoading === voice.voice_id" class="icon">&#8987;</span>
            <span v-else class="icon">&#9654;</span>
            {{ previewPlaying === voice.voice_id ? 'Stop' : previewLoading === voice.voice_id ? 'Loading...' : 'Preview' }}
          </button>
        </div>

        <div class="voice-notes-label">
          Notes
          <span class="voice-notes-saved" :class="{ show: noteSaved[voice.voice_id] }">Saved</span>
        </div>
        <textarea
          class="voice-notes-field"
          :value="voice.notes || ''"
          placeholder="Add notes about this voice (visible in voice selection dropdowns)..."
          @input="(e: Event) => onNoteInput(voice.voice_id, (e.target as HTMLTextAreaElement).value)"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-container {
  max-width: 720px;
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

.header {
  text-align: center;
  padding: 2rem 0 1.5rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  margin-bottom: 0;
}
.header h1 {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-weight: 300;
  font-size: 1.8rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.9);
}
.header p {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 0.95rem;
  font-weight: 300;
  font-style: italic;
  color: #555;
  margin-top: 0.4rem;
}

/* Tabs */
.tab-nav {
  display: flex;
  gap: 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  margin-bottom: 1.75rem;
}
.tab-btn {
  padding: 0.85rem 1.5rem;
  border: none;
  background: none;
  color: #555;
  font-family: inherit;
  font-size: 0.85rem;
  font-weight: 500;
  letter-spacing: 0.04em;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.25s;
}
.tab-btn:hover {
  color: #8a8a8a;
}
.tab-btn.active {
  color: rgba(255, 255, 255, 0.9);
  border-bottom-color: var(--color-accent);
}

/* Settings sections */
.settings-section {
  margin-bottom: 1.5rem;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 10px;
  padding: 1.3rem;
}
.settings-section h2 {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 1.05rem;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.9);
  margin-bottom: 0.5rem;
  letter-spacing: 0.03em;
}
.settings-section p {
  font-size: 0.8rem;
  color: #555;
  margin-bottom: 1rem;
  line-height: 1.5;
}
.settings-section code {
  background: rgba(255, 255, 255, 0.06);
  padding: 0.15rem 0.4rem;
  border-radius: 3px;
  font-size: 0.78rem;
  color: #8a8a8a;
}

.setting-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}
.setting-row label {
  font-size: 0.82rem;
  color: #8a8a8a;
  min-width: 110px;
  letter-spacing: 0.01em;
}

.select-input {
  padding: 0.5rem 0.75rem;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.2);
  color: #e8e6e3;
  font-family: inherit;
  font-size: 0.85rem;
  outline: none;
  transition: border-color 0.2s;
}
.select-input:focus {
  border-color: rgba(160, 32, 32, 0.4);
}

.save-btn {
  padding: 0.55rem 1.2rem;
  border: none;
  border-radius: 6px;
  background: var(--color-accent);
  color: #fff;
  font-family: inherit;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.25s;
  letter-spacing: 0.02em;
}
.save-btn:hover {
  background: var(--color-accent-hover);
}
.save-btn:disabled {
  background: rgba(255, 255, 255, 0.06);
  color: #555;
  cursor: not-allowed;
}

.upload-row {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  flex-wrap: wrap;
}
.file-input {
  font-size: 0.8rem;
  color: #8a8a8a;
}

/* Voice Library */
.voice-filter-row {
  display: flex;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
  flex-wrap: wrap;
}
.filter-group {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  flex: 1 1 130px;
  min-width: 0;
}
.filter-label {
  font-size: 0.68rem;
  color: #555;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.filter-select {
  padding: 0.45rem 0.65rem;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.35);
  color: #e8e6e3;
  font-family: inherit;
  font-size: 0.82rem;
  outline: none;
  cursor: pointer;
  transition: border-color 0.2s;
  width: 100%;
}
.filter-select:hover {
  border-color: rgba(255, 255, 255, 0.15);
}
.filter-select:focus {
  border-color: rgba(160, 32, 32, 0.4);
}
.voice-filter-count {
  font-size: 0.75rem;
  color: #555;
  margin-bottom: 0.75rem;
}

.empty {
  text-align: center;
  padding: 2rem;
  color: #555;
  font-size: 0.85rem;
}

.voice-card {
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 10px;
  padding: 1rem 1.2rem;
  margin-bottom: 0.75rem;
  transition: border-color 0.2s;
}
.voice-card:hover {
  border-color: rgba(255, 255, 255, 0.12);
}
.voice-card-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}
.voice-name {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 1rem;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.9);
}
.voice-badge {
  font-size: 0.65rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 0.15rem 0.45rem;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.06);
  color: #555;
}
.voice-badge.male {
  color: var(--color-info);
  background: rgba(104, 104, 184, 0.12);
}
.voice-badge.female {
  color: #b868b8;
  background: rgba(184, 104, 184, 0.12);
}
.voice-badge.other {
  color: #8ab868;
  background: rgba(138, 184, 104, 0.12);
}
.voice-badge.narrator {
  color: var(--color-success);
  background: rgba(58, 125, 92, 0.12);
}
.voice-archetypes {
  font-size: 0.78rem;
  color: #555;
  margin-bottom: 0.65rem;
  font-style: italic;
}

.voice-preview-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 0.6rem;
}
.preview-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.4rem 0.85rem;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.2);
  color: #8a8a8a;
  font-family: inherit;
  font-size: 0.78rem;
  cursor: pointer;
  transition: all 0.2s;
}
.preview-btn:hover {
  border-color: var(--color-accent);
  color: rgba(255, 255, 255, 0.9);
}
.preview-btn.loading {
  opacity: 0.5;
  cursor: wait;
}
.preview-btn .icon {
  font-size: 0.9rem;
}

.voice-notes-label {
  font-size: 0.72rem;
  color: #555;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.3rem;
}
.voice-notes-saved {
  font-size: 0.75rem;
  color: var(--color-success);
  opacity: 0;
  transition: opacity 0.3s;
  margin-left: 0.5rem;
}
.voice-notes-saved.show {
  opacity: 1;
}
.voice-notes-field {
  width: 100%;
  padding: 0.5rem 0.7rem;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.2);
  color: #e8e6e3;
  font-family: inherit;
  font-size: 0.82rem;
  outline: none;
  resize: vertical;
  min-height: 2.2rem;
  transition: border-color 0.2s;
}
.voice-notes-field:focus {
  border-color: rgba(255, 255, 255, 0.15);
}
.voice-notes-field::placeholder {
  color: #555;
  font-style: italic;
}
</style>
