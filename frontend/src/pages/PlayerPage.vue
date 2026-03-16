<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePlayerStore } from '@/stores/player'
import { usePlaylistStore } from '@/stores/playlist'
import { useNotificationStore } from '@/stores/notifications'
import { storiesApi, playerApi } from '@/api/client'
import type { SeriesPart } from '@/types'

const route = useRoute()
const router = useRouter()
const player = usePlayerStore()
const playlist = usePlaylistStore()
const notify = useNotificationStore()

const storyId = computed(() => Number(route.params.id))
const isSeeking = ref(false)
const seekValue = ref(0)
const seriesParts = ref<SeriesPart[]>([])
const storyRedditUrl = ref<string | null>(null)

// Browser tips
const showAndroidTip = ref(false)
const showIOSTip = ref(false)

// ── Formatted times ───────────────────────────────────────
function formatTime(seconds: number): string {
  if (!seconds || !isFinite(seconds)) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s < 10 ? '0' : ''}${s}`
}

const currentTimeFormatted = computed(() => formatTime(isSeeking.value ? seekValue.value : player.currentTime))
const durationFormatted = computed(() => formatTime(player.duration))
const progressPercent = computed(() => {
  if (isSeeking.value) return player.duration ? (seekValue.value / player.duration) * 100 : 0
  return player.duration ? (player.currentTime / player.duration) * 100 : 0
})

// ── Up next from playlist ─────────────────────────────────
const upNext = computed(() => {
  const items = playlist.items
  const idx = playlist.currentIndex
  return items.slice(idx + 1, idx + 6)
})

// ── Speed control ─────────────────────────────────────────
const speedDisplay = computed(() => player.playbackSpeed.toFixed(2))

function onSpeedSlider(e: Event) {
  const val = parseFloat((e.target as HTMLInputElement).value)
  player.setSpeed(val)
}

function onSpeedInput(e: Event) {
  const val = parseFloat((e.target as HTMLInputElement).value)
  if (!isNaN(val)) player.setSpeed(val)
}

// ── Progress bar ──────────────────────────────────────────
function onProgressInput(e: Event) {
  isSeeking.value = true
  const pct = parseFloat((e.target as HTMLInputElement).value)
  seekValue.value = (pct / 100) * (player.duration || 0)
}

function onProgressChange(e: Event) {
  const pct = parseFloat((e.target as HTMLInputElement).value)
  const time = (pct / 100) * (player.duration || 0)
  player.seek(time)
  isSeeking.value = false
}

// ── Repeat label ──────────────────────────────────────────
const repeatTitle = computed(() => {
  if (playlist.repeatMode === 'all') return 'Repeat: All'
  if (playlist.repeatMode === 'one') return 'Repeat: One'
  return 'Repeat: Off'
})

// ── Open playlist drawer ──────────────────────────────────
function openQueue() {
  const event = new CustomEvent('toggle-playlist-drawer')
  window.dispatchEvent(event)
}

// ── Load story and ensure playlist ────────────────────────
onMounted(async () => {
  const id = storyId.value

  // Ensure track is in playlist and set as current
  if (player.currentTrack) {
    playlist.ensureCurrent({
      storyId: id,
      title: player.currentTrack.title,
      author: player.currentTrack.author,
    })
  }

  // Load track if not already playing this one
  if (!player.currentTrack || player.currentTrack.id !== id) {
    await player.loadTrack(id, false)
    if (player.currentTrack) {
      playlist.ensureCurrent({
        storyId: id,
        title: player.currentTrack.title,
        author: player.currentTrack.author,
      })
    }
  }

  // Fetch story for reddit_url (for series matching)
  try {
    const story = await storiesApi.get(id)
    storyRedditUrl.value = story.reddit_url
  } catch { /* ignore */ }

  // Load series parts
  try {
    const data = await storiesApi.seriesParts(id)
    if (data.parts && data.parts.length >= 2) {
      seriesParts.value = data.parts
    }
  } catch { /* ignore */ }

  // Browser tips
  const ua = navigator.userAgent || ''
  const isIOS = /iPhone|iPad|iPod/.test(ua)
  const isAndroid = /Android/i.test(ua)
  const isStandalone =
    (navigator as unknown as { standalone?: boolean }).standalone === true ||
    window.matchMedia('(display-mode: standalone)').matches

  if (isIOS && !isStandalone && !localStorage.getItem('vttd_tip_ios_dismissed')) {
    showIOSTip.value = true
  } else if (isAndroid && !localStorage.getItem('vttd_tip_android_dismissed')) {
    showAndroidTip.value = true
  }
})

// Navigate to different player page when track changes via playlist next/prev
watch(
  () => player.currentTrack?.id,
  (newId) => {
    if (newId && newId !== storyId.value) {
      router.replace(`/story/${newId}/play`)
    }
  },
)

function dismissTip(platform: string) {
  localStorage.setItem(`vttd_tip_${platform}_dismissed`, '1')
  if (platform === 'ios') showIOSTip.value = false
  else showAndroidTip.value = false
}

function isCurrentPart(part: SeriesPart): boolean {
  if (!storyRedditUrl.value || !part.url) return false
  return storyRedditUrl.value.replace(/\/$/, '') === part.url.replace(/\/$/, '')
}
</script>

<template>
  <div class="page-player">
    <router-link to="/" class="back-link">&larr; All stories</router-link>

    <div class="player-container">
      <!-- Artwork with EQ visualizer -->
      <div class="artwork">
        <div class="eq-viz" aria-hidden="true">
          <div class="eq-bar" :class="{ paused: !player.isPlaying }" style="--d:1.2s;--h1:18%;--h2:68%;--h3:35%;--h4:82%;--h5:50%"></div>
          <div class="eq-bar" :class="{ paused: !player.isPlaying }" style="--d:0.85s;--h1:55%;--h2:22%;--h3:78%;--h4:15%;--h5:60%"></div>
          <div class="eq-bar" :class="{ paused: !player.isPlaying }" style="--d:1.4s;--h1:38%;--h2:88%;--h3:20%;--h4:65%;--h5:42%"></div>
          <div class="eq-bar glitch" :class="{ paused: !player.isPlaying }" style="--d:0.65s;--h1:72%;--h2:30%;--h3:92%;--h4:48%;--h5:80%"></div>
          <div class="eq-bar" :class="{ paused: !player.isPlaying }" style="--d:1.1s;--h1:48%;--h2:95%;--h3:28%;--h4:72%;--h5:35%"></div>
          <div class="eq-bar" :class="{ paused: !player.isPlaying }" style="--d:0.75s;--h1:82%;--h2:42%;--h3:68%;--h4:22%;--h5:55%"></div>
          <div class="eq-bar" :class="{ paused: !player.isPlaying }" style="--d:1.3s;--h1:28%;--h2:78%;--h3:52%;--h4:88%;--h5:18%"></div>
          <div class="eq-bar" :class="{ paused: !player.isPlaying }" style="--d:0.55s;--h1:62%;--h2:18%;--h3:82%;--h4:38%;--h5:72%"></div>
          <div class="eq-bar glitch" :class="{ paused: !player.isPlaying }" style="--d:0.95s;--h1:42%;--h2:72%;--h3:15%;--h4:58%;--h5:85%"></div>
          <div class="eq-bar" :class="{ paused: !player.isPlaying }" style="--d:0.7s;--h1:52%;--h2:12%;--h3:72%;--h4:32%;--h5:65%"></div>
          <div class="eq-bar" :class="{ paused: !player.isPlaying }" style="--d:1.15s;--h1:22%;--h2:62%;--h3:42%;--h4:85%;--h5:28%"></div>
        </div>
      </div>

      <!-- Story info -->
      <div class="story-info">
        <div class="story-title">{{ player.currentTrack?.title || 'Loading...' }}</div>
        <div class="story-meta">
          <template v-if="player.currentTrack?.author">by u/{{ player.currentTrack.author }} &middot; </template>
          {{ player.currentTrack?.part_count || 1 }} part{{ (player.currentTrack?.part_count || 1) !== 1 ? 's' : '' }}
        </div>
      </div>

      <!-- Progress bar -->
      <div class="progress-container">
        <input
          type="range"
          class="progress-bar"
          :value="progressPercent"
          min="0"
          max="100"
          step="0.1"
          @input="onProgressInput"
          @change="onProgressChange"
        />
        <div class="time-display">
          <span>{{ currentTimeFormatted }}</span>
          <span>{{ durationFormatted }}</span>
        </div>
      </div>

      <!-- Controls -->
      <div class="controls">
        <button
          class="control-btn small"
          :class="{ 'repeat-active': playlist.repeatMode !== 'off', 'repeat-one': playlist.repeatMode === 'one' }"
          :title="repeatTitle"
          @click="playlist.toggleRepeat()"
        >&#128257;<span class="repeat-one-dot">1</span></button>
        <button class="control-btn small" title="Previous" @click="playlist.prev()">&#9664;&#9664;</button>
        <button class="control-btn" title="Back 15s" @click="player.skipBack(15)">15 &#9664;&#9664;</button>
        <button class="control-btn play-btn" @click="player.togglePlay()">
          <span v-if="player.isPlaying">&#10074;&#10074;</span>
          <span v-else>&#9654;</span>
        </button>
        <button class="control-btn" title="Forward 15s" @click="player.skipForward(15)">&#9654;&#9654; 15</button>
        <button class="control-btn small" title="Next" @click="playlist.next()">&#9654;&#9654;</button>
        <button class="control-btn small" title="Queue" @click="openQueue">&#9776;</button>
      </div>

      <!-- Speed control -->
      <div class="speed-control">
        <span class="speed-label">Speed</span>
        <input
          type="range"
          class="speed-slider"
          min="0.5"
          max="3"
          step="0.05"
          :value="player.playbackSpeed"
          @input="onSpeedSlider"
        />
        <div class="speed-input-wrap">
          <input
            type="number"
            class="speed-input"
            min="0.5"
            max="3"
            step="0.05"
            :value="speedDisplay"
            @change="onSpeedInput"
            @keydown.enter="($event.target as HTMLInputElement).blur()"
          />
          <span class="speed-suffix">x</span>
        </div>
      </div>

      <!-- Secondary actions -->
      <div class="secondary-actions">
        <router-link :to="`/story/${storyId}`" class="btn-secondary">Script &amp; Settings</router-link>
        <a :href="playerApi.downloadUrl(storyId)" class="btn-secondary">Download MP3</a>
      </div>

      <!-- Up Next -->
      <div v-if="upNext.length" class="up-next-section">
        <div class="up-next-title">Up Next</div>
        <ul class="up-next-list">
          <li
            v-for="(item, i) in upNext"
            :key="i"
            class="up-next-item"
            @click="playlist.playAt(playlist.currentIndex + 1 + i)"
          >
            <span class="up-next-item-title">{{ item.title || 'Untitled' }}</span>
            <span v-if="item.author" class="up-next-item-author">u/{{ item.author }}</span>
          </li>
        </ul>
      </div>

      <!-- Series parts -->
      <div v-if="seriesParts.length" class="series-section">
        <div class="series-title">Series Parts</div>
        <ul class="series-list">
          <li v-for="(part, idx) in seriesParts" :key="idx">
            <div v-if="isCurrentPart(part)" class="series-part current">
              <span class="series-part-num">{{ idx + 1 }}</span>
              <span>{{ part.title || `Part ${idx + 1}` }} (current)</span>
            </div>
            <router-link
              v-else-if="part.story_id"
              :to="`/story/${part.story_id}/play`"
              class="series-part"
            >
              <span class="series-part-num">{{ idx + 1 }}</span>
              <span>{{ part.title || `Part ${idx + 1}` }}</span>
            </router-link>
            <router-link
              v-else
              :to="`/submit#url=${encodeURIComponent(part.url)}`"
              class="series-part"
            >
              <span class="series-part-num">{{ idx + 1 }}</span>
              <span>{{ part.title || `Part ${idx + 1}` }}</span>
            </router-link>
          </li>
        </ul>
      </div>

      <!-- Browser tips -->
      <div v-if="showAndroidTip" class="browser-tip">
        <button class="browser-tip-dismiss" @click="dismissTip('android')">&times;</button>
        <strong>Listening with screen locked?</strong> In Samsung Internet, enable
        <em>Settings &rarr; Useful Features &rarr; Background Play</em>.
        On any Android browser, set the browser to <em>Unrestricted</em> battery mode
        in your phone's app settings.
      </div>
      <div v-if="showIOSTip" class="browser-tip">
        <button class="browser-tip-dismiss" @click="dismissTip('ios')">&times;</button>
        <strong>For the best experience on iPhone:</strong> Tap the share button
        and choose <em>Add to Home Screen</em>. This gives you lock-screen controls
        and background playback without Safari's toolbar.
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-player {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 1.25rem;
}
.page-player .back-link { align-self: flex-start; }

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

.player-container {
  width: 100%;
  max-width: 480px;
  margin-top: 1.5rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.75rem;
}

/* ── Artwork ─────────────────────────────────── */
.artwork {
  width: 280px;
  height: 280px;
  border-radius: var(--radius-xl);
  background:
    radial-gradient(ellipse at 30% 40%, rgba(160,32,32,0.12) 0%, transparent 60%),
    radial-gradient(ellipse at 70% 60%, rgba(40,10,40,0.2) 0%, transparent 50%),
    radial-gradient(ellipse at 50% 50%, #0c0808 0%, #060410 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  box-shadow:
    0 24px 80px rgba(0,0,0,0.7),
    0 0 0 1px rgba(255,255,255,0.04);
}
.artwork::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at 50% 50%, transparent 30%, rgba(0,0,0,0.5) 100%);
}

/* ── EQ Visualizer ───────────────────────────── */
.eq-viz {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: 2.5px;
  height: 90px;
  width: 120px;
  padding-bottom: 4px;
}
.eq-bar {
  flex: 1;
  min-height: 3px;
  border-radius: 1px;
  background: linear-gradient(to top, var(--color-accent), rgba(160,32,32,0.25));
  box-shadow: 0 0 8px rgba(160,32,32,0.15);
  animation: eq-pulse var(--d, 1s) steps(8, end) infinite;
}
.eq-bar.paused {
  animation-play-state: paused;
}
.eq-bar.glitch {
  animation:
    eq-pulse var(--d, 1s) steps(8, end) infinite,
    eq-glitch 6s ease-in-out infinite;
}
.eq-bar.glitch.paused {
  animation-play-state: paused, paused;
}
@keyframes eq-pulse {
  0%, 100% { height: var(--h1); opacity: 0.65; }
  20%  { height: var(--h2); opacity: 0.85; }
  40%  { height: var(--h3); opacity: 0.55; }
  60%  { height: var(--h4); opacity: 0.9; }
  80%  { height: var(--h5, var(--h2)); opacity: 0.7; }
}
@keyframes eq-glitch {
  0%, 92%, 100% { filter: brightness(1); }
  93%  { filter: brightness(2.5); opacity: 0.3; }
  94%  { filter: brightness(0.3); }
  95%  { filter: brightness(1.8); opacity: 1; }
}
.eq-viz::after {
  content: '';
  position: absolute;
  inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 128 128' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='1'/%3E%3C/svg%3E");
  opacity: 0.14;
  mix-blend-mode: overlay;
  pointer-events: none;
  animation: eq-static 0.12s steps(2) infinite;
}
@keyframes eq-static {
  0%   { transform: translate(0, 0); }
  100% { transform: translate(-5%, -8%); }
}

/* ── Story info ──────────────────────────────── */
.story-info { text-align: center; width: 100%; }
.story-title {
  font-family: var(--font-family-serif);
  font-size: 1.35rem;
  font-weight: 500;
  color: var(--color-text-1);
  line-height: 1.3;
}
.story-meta {
  font-size: 0.8rem;
  color: var(--color-text-3);
  margin-top: 0.35rem;
  letter-spacing: 0.02em;
}

/* ── Progress bar ────────────────────────────── */
.progress-container { width: 100%; padding: 0 0.25rem; }
.progress-bar {
  width: 100%; height: 5px;
  -webkit-appearance: none; appearance: none;
  background: transparent; cursor: pointer; outline: none;
}
.progress-bar::-webkit-slider-runnable-track {
  height: 5px; border-radius: 3px;
  background: rgba(255,255,255,0.08);
}
.progress-bar::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 16px; height: 16px; border-radius: 50%;
  background: var(--color-accent);
  margin-top: -5.5px;
  box-shadow: 0 0 12px rgba(160,32,32,0.4);
  transition: transform 0.15s;
}
.progress-bar::-webkit-slider-thumb:hover { transform: scale(1.2); }
.progress-bar::-moz-range-track {
  height: 5px; border-radius: 3px;
  background: rgba(255,255,255,0.08); border: none;
}
.progress-bar::-moz-range-thumb {
  width: 16px; height: 16px; border-radius: 50%;
  background: var(--color-accent); border: none;
  box-shadow: 0 0 12px rgba(160,32,32,0.4);
}
.time-display {
  display: flex; justify-content: space-between;
  font-size: 0.7rem; color: var(--color-text-3);
  margin-top: 0.4rem;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.03em;
}

/* ── Controls ────────────────────────────────── */
.controls {
  display: flex; align-items: center; justify-content: center; gap: 1.5rem;
}
.control-btn {
  background: none; border: none; color: var(--color-text-2);
  cursor: pointer; padding: 0.5rem; font-size: 1.2rem;
  transition: all 0.2s; -webkit-tap-highlight-color: transparent;
}
.control-btn:hover { color: var(--color-text-1); }
.control-btn.small { font-size: 0.95rem; }
.control-btn.repeat-active { color: var(--color-accent); }
.control-btn .repeat-one-dot {
  display: none; font-size: 0.55rem;
  vertical-align: super; font-weight: 700;
}
.control-btn.repeat-one .repeat-one-dot { display: inline; }
.play-btn {
  width: 68px; height: 68px; border-radius: 50%;
  background: var(--color-accent); color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.5rem;
  box-shadow: 0 4px 24px rgba(160,32,32,0.35), 0 0 0 1px rgba(255,255,255,0.05);
  transition: all 0.25s;
}
.play-btn:hover {
  background: var(--color-accent-hover);
  box-shadow: 0 6px 32px rgba(160,32,32,0.45), 0 0 0 1px rgba(255,255,255,0.08);
  transform: scale(1.04);
}
.play-btn:active { transform: scale(0.96); }

/* ── Speed control ───────────────────────────── */
.speed-control {
  width: 100%; display: flex; align-items: center;
  gap: 0.75rem; padding: 0 0.5rem;
}
.speed-label {
  font-size: 0.75rem; color: var(--color-text-3);
  white-space: nowrap; min-width: 2.5rem;
  letter-spacing: 0.04em; text-transform: uppercase;
}
.speed-slider {
  flex: 1; height: 3px;
  -webkit-appearance: none; appearance: none;
  background: transparent; cursor: pointer; outline: none;
}
.speed-slider::-webkit-slider-runnable-track {
  height: 3px; border-radius: 2px; background: rgba(255,255,255,0.08);
}
.speed-slider::-webkit-slider-thumb {
  -webkit-appearance: none; width: 12px; height: 12px;
  border-radius: 50%; background: var(--color-text-2);
  margin-top: -4.5px; transition: background 0.2s;
}
.speed-slider::-webkit-slider-thumb:hover { background: var(--color-accent); }
.speed-slider::-moz-range-track {
  height: 3px; border-radius: 2px;
  background: rgba(255,255,255,0.08); border: none;
}
.speed-slider::-moz-range-thumb {
  width: 12px; height: 12px; border-radius: 50%;
  background: var(--color-text-2); border: none;
}
.speed-slider::-moz-range-thumb:hover { background: var(--color-accent); }
.speed-input-wrap { display: flex; align-items: center; gap: 0.15rem; }
.speed-input {
  width: 3.2rem; background: var(--color-surface);
  border: 1px solid var(--color-border); border-radius: var(--radius-sm);
  color: var(--color-text-1); font-family: var(--font-family-sans);
  font-size: 0.8rem; padding: 0.3rem; text-align: center;
  font-variant-numeric: tabular-nums; outline: none;
  transition: border-color 0.2s; -moz-appearance: textfield;
}
.speed-input::-webkit-inner-spin-button,
.speed-input::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
.speed-input:focus { border-color: var(--color-border-focus); }
.speed-suffix { font-size: 0.75rem; color: var(--color-text-3); }

/* ── Secondary actions ───────────────────────── */
.secondary-actions { display: flex; gap: 1rem; }
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

/* ── Browser tips ────────────────────────────── */
.browser-tip {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 0.85rem 1.1rem;
  font-size: 0.78rem;
  color: var(--color-text-3);
  width: 100%;
  line-height: 1.5;
}
.browser-tip strong { color: var(--color-text-2); }
.browser-tip-dismiss {
  background: none; border: none; color: var(--color-text-3);
  float: right; cursor: pointer; font-size: 1rem;
  padding: 0; margin: -0.25rem 0 0 0.5rem; transition: color 0.15s;
}
.browser-tip-dismiss:hover { color: var(--color-text-2); }

/* ── Up Next ─────────────────────────────────── */
.up-next-section { width: 100%; margin-top: 0.5rem; }
.up-next-title {
  font-family: var(--font-family-serif);
  font-size: 0.95rem; font-weight: 500;
  color: var(--color-text-2);
  margin-bottom: 0.6rem; letter-spacing: 0.04em;
}
.up-next-list {
  list-style: none; display: flex;
  flex-direction: column; gap: 0.35rem;
}
.up-next-item {
  display: flex; align-items: center; gap: 0.6rem;
  padding: 0.5rem 0.85rem;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  cursor: pointer; transition: all 0.2s;
}
.up-next-item:hover {
  border-color: var(--color-border-hover);
  background: var(--color-surface-hover);
}
.up-next-item-title {
  font-size: 0.82rem; color: var(--color-text-1);
  flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.up-next-item-author {
  font-size: 0.7rem; color: var(--color-text-3); flex-shrink: 0;
}

/* ── Series parts ────────────────────────────── */
.series-section { width: 100%; margin-top: 0.5rem; }
.series-title {
  font-family: var(--font-family-serif);
  font-size: 0.95rem; font-weight: 500;
  color: var(--color-text-2);
  margin-bottom: 0.6rem; letter-spacing: 0.04em;
}
.series-list {
  list-style: none; display: flex;
  flex-direction: column; gap: 0.4rem;
}
.series-part {
  display: flex; align-items: center; gap: 0.6rem;
  padding: 0.55rem 0.85rem;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  text-decoration: none; color: var(--color-text-2);
  font-size: 0.8rem; transition: all 0.2s;
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
</style>
