<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storiesApi, audioApi } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { usePlaylistStore } from '@/stores/playlist'
import { useNotificationStore } from '@/stores/notifications'
import { ApiError } from '@/api/client'
import type { Story, SeriesPartsResponse } from '@/types'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const playlist = usePlaylistStore()
const notify = useNotificationStore()

const story = ref<Story | null>(null)
const loading = ref(true)
const scriptInfo = ref<{ segment_count: number; voice_segments: number; sfx_segments: number } | null>(null)
const hasScript = ref(false)
const hasAudio = ref(false)
const series = ref<SeriesPartsResponse | null>(null)
const resumeSeconds = ref(0)

// Generation state
const generatingScript = ref(false)
const scriptStatus = ref({ text: '', type: '' })
const generatingAudio = ref(false)
const audioStatus = ref({ text: '', type: '' })

const storyId = computed(() => Number(route.params.id))

const wordCount = computed(() => {
  const text = story.value?.narration_text || ''
  return text ? text.split(/\s+/).length : 0
})
const estMinutes = computed(() => Math.ceil(wordCount.value / 150))
const teaser = computed(() => {
  const text = story.value?.narration_text || ''
  if (!text) return ''
  return text.slice(0, 200).replace(/\s+\S*$/, '') + '...'
})

onMounted(async () => {
  try {
    story.value = await storiesApi.get(storyId.value)
    hasAudio.value = !!story.value.audio_file_path

    // Fetch script info
    try {
      const info = await audioApi.getScript(storyId.value)
      hasScript.value = true
      scriptInfo.value = {
        segment_count: info.segment_count,
        voice_segments: info.voice_segments,
        sfx_segments: info.sfx_segments,
      }
    } catch {
      hasScript.value = false
    }

    // Fetch resume position
    if (hasAudio.value && auth.isLoggedIn) {
      try {
        const pb = await storiesApi.getPlayback(storyId.value)
        resumeSeconds.value = pb.position_seconds
      } catch { /* no saved position */ }
    }

    // Fetch series parts
    try {
      const data = await storiesApi.seriesParts(storyId.value)
      if (data.parts.length >= 2) series.value = data
    } catch { /* no series */ }
  } catch {
    notify.show('Failed to load story', 'error')
  } finally {
    loading.value = false
  }
})

async function generateScript() {
  generatingScript.value = true
  scriptStatus.value = { text: 'Claude is analyzing the story and building a narration script...', type: '' }
  try {
    await audioApi.generateScript(storyId.value)
    scriptStatus.value = { text: 'Script generated! Reloading...', type: 'success' }
    setTimeout(() => router.go(0), 800)
  } catch (e) {
    const body = (e instanceof ApiError ? e.body : null) as { detail?: string } | null
    scriptStatus.value = { text: body?.detail || 'Script generation failed', type: 'error' }
    generatingScript.value = false
  }
}

async function generateAudio(force = false) {
  if (force && !confirm('Regenerate audio? This will replace the current audio file.')) return
  generatingAudio.value = true
  audioStatus.value = { text: 'Generating multi-voice audio with SFX and ambient sound...', type: '' }
  try {
    await audioApi.generateNarration(storyId.value, null, force)
    audioStatus.value = { text: 'Audio generated! Reloading...', type: 'success' }
    setTimeout(() => router.go(0), 800)
  } catch (e) {
    const body = (e instanceof ApiError ? e.body : null) as { detail?: string } | null
    audioStatus.value = { text: body?.detail || 'Audio generation failed', type: 'error' }
    generatingAudio.value = false
  }
}

function formatTime(secs: number) {
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

function addToQueue() {
  if (!story.value) return
  playlist.addToEnd({ storyId: story.value.id, title: story.value.title, author: story.value.author || '' })
  notify.show('Added to queue')
}

function playNextFn() {
  if (!story.value) return
  playlist.addNext({ storyId: story.value.id, title: story.value.title, author: story.value.author || '' })
  notify.show('Playing next')
}
</script>

<template>
  <div class="page-container">
    <router-link to="/" class="back-link">&larr; All stories</router-link>

    <div v-if="loading" class="text-center py-16"><span class="spinner spinner-lg"></span></div>

    <template v-else-if="story">
      <!-- Header -->
      <div class="story-header">
        <div class="story-title">{{ story.title }}</div>
        <div class="story-meta">
          <span v-if="story.author">by u/{{ story.author }}</span>
          <span>{{ story.part_count }} part{{ story.part_count !== 1 ? 's' : '' }}</span>
          <a v-if="story.reddit_url" :href="story.reddit_url" target="_blank" rel="noopener">View on Reddit</a>
        </div>
        <div v-if="teaser" class="story-teaser">{{ teaser }}</div>
        <div class="story-stats">
          <div v-if="wordCount" class="stat"><span class="stat-value">{{ wordCount.toLocaleString() }}</span> words</div>
          <div v-if="estMinutes" class="stat">~<span class="stat-value">{{ estMinutes }}</span> min listen</div>
        </div>
        <div v-if="resumeSeconds > 0 && hasAudio" class="resume-info">
          Previously listened to {{ formatTime(resumeSeconds) }}
        </div>
      </div>

      <!-- Pipeline -->
      <div class="pipeline">
        <!-- Step 1: Fetched -->
        <div class="step">
          <div class="step-header">
            <div class="step-number done">&#10003;</div>
            <div class="step-title">Story Fetched</div>
          </div>
          <div class="step-body">
            <div class="step-info">{{ (story.narration_text || '').length }} characters of narration text</div>
            <div v-if="story.narration_text" style="margin-top:0.5rem">
              <router-link :to="`/story/${story.id}/read`" class="btn-secondary">Read Story</router-link>
            </div>
          </div>
        </div>

        <!-- Step 2: Script -->
        <div class="step">
          <div class="step-header">
            <div class="step-number" :class="generatingScript ? 'active' : hasScript ? 'done' : 'pending'">
              <template v-if="hasScript">&#10003;</template><template v-else>2</template>
            </div>
            <div class="step-title">Narration Script</div>
          </div>
          <div class="step-body">
            <template v-if="hasScript && scriptInfo">
              <div class="step-info">
                Script generated with {{ scriptInfo.segment_count }} segments ({{ scriptInfo.voice_segments }} voice, {{ scriptInfo.sfx_segments }} SFX)
              </div>
              <div style="margin-top:0.5rem">
                <router-link :to="`/story/${story.id}/edit`" class="btn-secondary">Edit Script</router-link>
              </div>
            </template>
            <template v-else-if="auth.isLoggedIn">
              <button class="btn-primary" :disabled="generatingScript" @click="generateScript">
                <span v-if="generatingScript" class="spinner"></span>
                {{ generatingScript ? 'Generating...' : 'Generate Script' }}
              </button>
              <div v-if="scriptStatus.text" class="step-status" :class="scriptStatus.type">{{ scriptStatus.text }}</div>
            </template>
            <div v-else class="login-prompt"><router-link to="/login">Sign in</router-link> to generate scripts</div>
          </div>
        </div>

        <!-- Step 3: Audio -->
        <div class="step">
          <div class="step-header">
            <div class="step-number" :class="generatingAudio ? 'active' : hasAudio ? 'done' : 'pending'">
              <template v-if="hasAudio">&#10003;</template><template v-else>3</template>
            </div>
            <div class="step-title">Audio Narration</div>
          </div>
          <div class="step-body">
            <template v-if="hasAudio">
              <div class="step-info step-status success">Audio ready</div>
              <div v-if="auth.isLoggedIn" style="margin-top:0.5rem">
                <button class="btn-secondary" :disabled="generatingAudio" @click="generateAudio(true)">
                  <span v-if="generatingAudio" class="spinner"></span>
                  {{ generatingAudio ? 'Regenerating...' : 'Regenerate Audio' }}
                </button>
              </div>
              <div v-if="audioStatus.text" class="step-status" :class="audioStatus.type">{{ audioStatus.text }}</div>
            </template>
            <template v-else-if="auth.isLoggedIn">
              <button class="btn-primary" :disabled="!hasScript || generatingAudio" @click="generateAudio(false)">
                <span v-if="generatingAudio" class="spinner"></span>
                {{ generatingAudio ? 'Generating...' : 'Generate Audio' }}
              </button>
              <div v-if="!hasScript" class="step-info">Generate a script first</div>
              <div v-if="audioStatus.text" class="step-status" :class="audioStatus.type">
                {{ audioStatus.text }}
                <div v-if="!audioStatus.type" class="progress-bar-track"><div class="progress-bar-fill"></div></div>
              </div>
            </template>
            <div v-else class="login-prompt"><router-link to="/login">Sign in</router-link> to generate audio</div>
          </div>
        </div>
      </div>

      <!-- Listen section -->
      <div v-if="hasAudio" class="listen-section">
        <router-link :to="`/story/${story.id}/play`" class="listen-btn">&#9654; Listen Now</router-link>
        <div class="queue-actions">
          <button class="btn-secondary" @click="addToQueue">Add to Queue</button>
          <button class="btn-secondary" @click="playNextFn">Play Next</button>
        </div>
      </div>

      <!-- Series parts -->
      <div v-if="series" class="series-section">
        <div class="series-title">
          Series Parts
          <span v-if="series.series_word_count" class="series-stats">
            {{ series.series_word_count.toLocaleString() }} words &middot; ~{{ series.series_est_minutes }} min listen
          </span>
        </div>
        <ul class="series-list">
          <li v-for="(part, idx) in series.parts" :key="part.url">
            <div v-if="part.url === story.reddit_url" class="series-part current">
              <span class="series-part-num">{{ idx + 1 }}</span>
              <span>{{ part.title || 'Part ' + (idx + 1) }} (current)</span>
            </div>
            <router-link v-else-if="part.story_id" :to="`/story/${part.story_id}`" class="series-part">
              <span class="series-part-num">{{ idx + 1 }}</span>
              <span>{{ part.title || 'Part ' + (idx + 1) }}</span>
            </router-link>
            <div v-else class="series-part" style="opacity:0.5">
              <span class="series-part-num">{{ idx + 1 }}</span>
              <span>{{ part.title || 'Part ' + (idx + 1) }}</span>
            </div>
          </li>
        </ul>
      </div>
    </template>
  </div>
</template>

<style scoped>
.back-link {
  display: inline-flex; align-items: center; gap: 0.4rem; color: var(--color-text-3);
  text-decoration: none; font-size: 0.8rem; padding: 0.5rem 0; transition: color 0.2s;
  letter-spacing: 0.03em; text-transform: uppercase;
}
.back-link:hover { color: var(--color-text-2); }
.story-header { padding: 2rem 0; border-bottom: 1px solid var(--color-border); margin-bottom: 1.75rem; }
.story-title { font-family: var(--font-family-serif); font-size: 1.8rem; font-weight: 500; color: var(--color-text-1); line-height: 1.3; }
.story-meta { font-size: 0.8rem; color: var(--color-text-3); margin-top: 0.5rem; display: flex; gap: 1rem; flex-wrap: wrap; }
.story-meta a { color: var(--color-text-2); text-decoration: none; transition: color 0.2s; }
.story-meta a:hover { color: var(--color-text-1); }
.story-teaser {
  margin-top: 1.25rem; font-family: var(--font-family-serif); font-size: 1rem; font-style: italic;
  font-weight: 300; color: var(--color-text-2); line-height: 1.6;
  border-left: 2px solid rgba(160,32,32,0.25); padding-left: 1.1rem;
}
.story-stats { display: flex; gap: 1.5rem; margin-top: 1rem; flex-wrap: wrap; }
.stat { font-size: 0.78rem; color: var(--color-text-3); }
.stat-value { color: var(--color-text-2); font-weight: 600; }
.resume-info {
  margin-top: 0.75rem; font-size: 0.8rem; color: var(--color-info);
  background: var(--color-info-dim); border: 1px solid rgba(104,104,184,0.15);
  border-radius: var(--radius-sm); padding: 0.5rem 0.85rem; display: inline-block;
}
.pipeline { display: flex; flex-direction: column; gap: 0.75rem; }
.step {
  background: var(--color-surface); border: 1px solid var(--color-border);
  border-radius: var(--radius-md); padding: 1.1rem 1.3rem; backdrop-filter: blur(12px);
}
.step-header { display: flex; align-items: center; gap: 0.8rem; }
.step-number {
  width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
  font-size: 0.75rem; font-weight: 700; flex-shrink: 0; transition: all 0.3s;
}
.step-number.done { background: var(--color-success-dim); color: var(--color-success); border: 1px solid rgba(58,125,92,0.2); }
.step-number.pending { background: var(--color-surface); color: var(--color-text-3); border: 1px solid var(--color-border); }
.step-number.active { background: var(--color-accent-dim); color: var(--color-accent); border: 1px solid rgba(160,32,32,0.25); box-shadow: 0 0 16px rgba(160,32,32,0.15); }
.step-title { font-family: var(--font-family-serif); font-size: 1.3rem; font-weight: 500; color: var(--color-text-1); flex: 1; }
.step-body { margin-top: 0.75rem; padding-left: 2.8rem; }
.step-info { font-size: 0.78rem; color: var(--color-text-3); margin-top: 0.4rem; }
.step-status { font-size: 0.8rem; color: var(--color-text-3); margin-top: 0.5rem; }
.step-status.error { color: #e07070; }
.step-status.success { color: var(--color-success); }
.login-prompt { text-align: center; padding: 1rem; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); font-size: 0.85rem; color: var(--color-text-2); }
.login-prompt a { color: var(--color-accent); text-decoration: none; font-weight: 600; }
.listen-section { margin-top: 2rem; text-align: center; }
.listen-btn {
  display: inline-flex; align-items: center; gap: 0.6rem; padding: 1rem 2.5rem;
  border: none; border-radius: var(--radius-lg); background: var(--color-accent); color: #fff;
  font-family: var(--font-family-serif); font-size: 1.2rem; font-weight: 600; cursor: pointer;
  text-decoration: none; letter-spacing: 0.04em;
  box-shadow: 0 6px 32px rgba(160,32,32,0.3), 0 0 0 1px rgba(255,255,255,0.05);
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.listen-btn:hover { background: var(--color-accent-hover); box-shadow: 0 8px 40px rgba(160,32,32,0.4); transform: translateY(-1px); }
.queue-actions { display: flex; gap: 0.75rem; justify-content: center; margin-top: 0.75rem; }
.progress-bar-track { width: 100%; height: 3px; background: rgba(255,255,255,0.06); border-radius: 2px; margin-top: 0.6rem; overflow: hidden; }
.progress-bar-fill { height: 100%; background: var(--color-accent); border-radius: 2px; width: 0%; animation: indeterminate 1.8s cubic-bezier(0.65, 0, 0.35, 1) infinite; }
@keyframes indeterminate { 0% { width: 0%; margin-left: 0; } 50% { width: 35%; margin-left: 35%; } 100% { width: 0%; margin-left: 100%; } }
.series-section { margin-top: 2rem; }
.series-title { font-family: var(--font-family-serif); font-size: 1rem; font-weight: 500; color: var(--color-text-2); margin-bottom: 0.6rem; display: flex; align-items: baseline; gap: 0.6rem; flex-wrap: wrap; }
.series-stats { font-family: var(--font-family-sans); font-size: 0.78rem; font-weight: 400; color: var(--color-text-3); }
.series-list { list-style: none; display: flex; flex-direction: column; gap: 0.4rem; }
.series-part {
  display: flex; align-items: center; gap: 0.6rem; padding: 0.55rem 0.85rem;
  background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-sm);
  text-decoration: none; color: var(--color-text-2); font-size: 0.82rem; transition: all 0.2s;
}
.series-part:hover { border-color: var(--color-border-hover); background: var(--color-surface-hover); }
.series-part.current { border-color: rgba(160,32,32,0.3); background: var(--color-accent-dim); }
.series-part-num { font-weight: 600; color: var(--color-text-3); min-width: 1.5rem; text-align: center; }
</style>
