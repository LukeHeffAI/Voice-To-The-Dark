<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePlayerStore } from '../stores/player'
import { usePlaylistStore } from '../stores/playlist'
import { formatTime } from '../composables/useFormatTime'
import { downloadUrl } from '../api/player'
import EqVisualizer from '../components/EqVisualizer.vue'
import SeriesParts from '../components/SeriesParts.vue'

const route = useRoute()
const router = useRouter()
const player = usePlayerStore()
const playlist = usePlaylistStore()

const storyId = computed(() => Number(route.params.id))
const isSeeking = ref(false)
const seekValue = ref(0)
const showAndroidTip = ref(false)
const showIosTip = ref(false)

onMounted(() => {
  const id = storyId.value
  playlist.ensureCurrent({ storyId: id, title: player.title || '', author: player.author || '' })

  if (player.storyId !== id) {
    player.loadTrack(id, '', '', false)
  }

  // Browser tips
  const ua = navigator.userAgent || ''
  const isIOS = /iPhone|iPad|iPod/.test(ua)
  const isAndroid = /Android/i.test(ua)
  const isStandalone =
    (navigator as unknown as { standalone?: boolean }).standalone === true ||
    window.matchMedia('(display-mode: standalone)').matches

  if (isIOS && !isStandalone && !localStorage.getItem('vttd_tip_ios_dismissed')) {
    showIosTip.value = true
  } else if (isAndroid && !localStorage.getItem('vttd_tip_android_dismissed')) {
    showAndroidTip.value = true
  }
})

// Navigate to new player page when playlist changes track
watch(
  () => player.storyId,
  (newId) => {
    if (newId && newId !== storyId.value) {
      router.push({ name: 'player', params: { id: newId } })
    }
  },
)

const progressPct = computed(() => {
  if (isSeeking.value) return seekValue.value
  if (!player.duration) return 0
  return (player.currentTime / player.duration) * 100
})

function onSeekInput(e: Event) {
  isSeeking.value = true
  seekValue.value = Number((e.target as HTMLInputElement).value)
}

function onSeekChange(e: Event) {
  const pct = Number((e.target as HTMLInputElement).value)
  const time = (pct / 100) * (player.duration || 0)
  player.seek(time)
  isSeeking.value = false
}

const seekTimeDisplay = computed(() => {
  if (isSeeking.value) {
    return formatTime((seekValue.value / 100) * (player.duration || 0))
  }
  return formatTime(player.currentTime)
})

function onSpeedSlider(e: Event) {
  player.setSpeed(Number((e.target as HTMLInputElement).value))
}

function onSpeedInput(e: Event) {
  player.setSpeed(Number((e.target as HTMLInputElement).value))
}

function dismissTip(platform: string) {
  localStorage.setItem(`vttd_tip_${platform}_dismissed`, '1')
  if (platform === 'ios') showIosTip.value = false
  else showAndroidTip.value = false
}

const repeatLabel = computed(() => {
  if (playlist.repeatMode === 'all') return 'Repeat: All'
  if (playlist.repeatMode === 'one') return 'Repeat: One'
  return 'Repeat: Off'
})

const upNextItems = computed(() => {
  const start = playlist.currentIndex + 1
  return playlist.items.slice(start, start + 5)
})
</script>

<template>
  <div class="page-player">
    <RouterLink to="/" class="back-link">&larr; All stories</RouterLink>

    <div class="player-container">
      <EqVisualizer />

      <div class="story-info">
        <div class="story-title">{{ player.title || 'Loading...' }}</div>
        <div class="story-meta">
          <span v-if="player.author">by u/{{ player.author }}</span>
        </div>
      </div>

      <div class="progress-container">
        <input
          type="range"
          class="progress-bar"
          :value="progressPct"
          min="0"
          max="100"
          step="0.1"
          @input="onSeekInput"
          @change="onSeekChange"
        />
        <div class="time-display">
          <span>{{ seekTimeDisplay }}</span>
          <span>{{ formatTime(player.duration) }}</span>
        </div>
      </div>

      <div class="controls">
        <button
          class="control-btn small"
          :class="{ 'repeat-active': playlist.repeatMode !== 'off', 'repeat-one': playlist.repeatMode === 'one' }"
          :title="repeatLabel"
          @click="playlist.toggleRepeat()"
        >
          &#128257;<span class="repeat-one-dot">1</span>
        </button>
        <button class="control-btn small" title="Previous" @click="playlist.prev()">&#9664;&#9664;</button>
        <button class="control-btn" title="Back 15s" @click="player.skip(-15)">15 &#9664;&#9664;</button>
        <button class="control-btn play-btn" @click="player.togglePlay()">
          <span v-if="player.isPlaying">&#10074;&#10074;</span>
          <span v-else>&#9654;</span>
        </button>
        <button class="control-btn" title="Forward 15s" @click="player.skip(15)">15 &#9654;&#9654;</button>
        <button class="control-btn small" title="Next" @click="playlist.next()">&#9654;&#9654;</button>
      </div>

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
            :value="player.playbackSpeed.toFixed(2)"
            @change="onSpeedInput"
          />
          <span class="speed-suffix">x</span>
        </div>
      </div>

      <div class="secondary-actions">
        <RouterLink :to="{ name: 'story-detail', params: { id: storyId } }" class="btn-secondary">
          Script &amp; Settings
        </RouterLink>
        <a :href="downloadUrl(storyId)" class="btn-secondary">Download MP3</a>
      </div>

      <!-- Up Next -->
      <div v-if="upNextItems.length > 0" class="up-next-section">
        <div class="up-next-title">Up Next</div>
        <ul class="up-next-list">
          <li
            v-for="(track, i) in upNextItems"
            :key="track.storyId"
            class="up-next-item"
            @click="playlist.playAt(playlist.currentIndex + 1 + i)"
          >
            <span class="up-next-item-title">{{ track.title || 'Untitled' }}</span>
            <span v-if="track.author" class="up-next-item-author">u/{{ track.author }}</span>
          </li>
        </ul>
      </div>

      <!-- Series parts -->
      <div class="series-wrap">
        <SeriesParts :story-id="storyId" />
      </div>

      <!-- Browser tips -->
      <div v-if="showAndroidTip" class="browser-tip">
        <button class="browser-tip-dismiss" @click="dismissTip('android')">&times;</button>
        <strong>Listening with screen locked?</strong> In Samsung Internet, enable
        <em>Settings &rarr; Useful Features &rarr; Background Play</em>.
        On any Android browser, set the browser to <em>Unrestricted</em> battery mode
        in your phone's app settings.
      </div>
      <div v-if="showIosTip" class="browser-tip">
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
.page-player .back-link {
  align-self: flex-start;
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

.player-container {
  width: 100%;
  max-width: 480px;
  margin-top: 1.5rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.75rem;
}

.story-info {
  text-align: center;
  width: 100%;
}
.story-title {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 1.35rem;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.9);
  line-height: 1.3;
}
.story-meta {
  font-size: 0.8rem;
  color: #555;
  margin-top: 0.35rem;
  letter-spacing: 0.02em;
}

/* Progress bar */
.progress-container {
  width: 100%;
  padding: 0 0.25rem;
}
.progress-bar {
  width: 100%;
  height: 5px;
  -webkit-appearance: none;
  appearance: none;
  background: transparent;
  cursor: pointer;
  outline: none;
}
.progress-bar::-webkit-slider-runnable-track {
  height: 5px;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.08);
}
.progress-bar::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--color-accent);
  margin-top: -5.5px;
  box-shadow: 0 0 12px rgba(160, 32, 32, 0.4);
  transition: transform 0.15s;
}
.progress-bar::-webkit-slider-thumb:hover {
  transform: scale(1.2);
}
.progress-bar::-moz-range-track {
  height: 5px;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.08);
  border: none;
}
.progress-bar::-moz-range-thumb {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--color-accent);
  border: none;
  box-shadow: 0 0 12px rgba(160, 32, 32, 0.4);
}
.time-display {
  display: flex;
  justify-content: space-between;
  font-size: 0.7rem;
  color: #555;
  margin-top: 0.4rem;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.03em;
}

/* Controls */
.controls {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1.5rem;
}
.control-btn {
  background: none;
  border: none;
  color: #8a8a8a;
  cursor: pointer;
  padding: 0.5rem;
  font-size: 1.2rem;
  transition: all 0.2s;
  -webkit-tap-highlight-color: transparent;
}
.control-btn:hover {
  color: rgba(255, 255, 255, 0.9);
}
.control-btn.small {
  font-size: 0.95rem;
}
.control-btn.repeat-active {
  color: var(--color-accent);
}
.control-btn .repeat-one-dot {
  display: none;
  font-size: 0.55rem;
  vertical-align: super;
  font-weight: 700;
}
.control-btn.repeat-one .repeat-one-dot {
  display: inline;
}
.play-btn {
  width: 68px;
  height: 68px;
  border-radius: 50%;
  background: var(--color-accent);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
  box-shadow:
    0 4px 24px rgba(160, 32, 32, 0.35),
    0 0 0 1px rgba(255, 255, 255, 0.05);
  transition: all 0.25s;
}
.play-btn:hover {
  background: var(--color-accent-hover);
  box-shadow:
    0 6px 32px rgba(160, 32, 32, 0.45),
    0 0 0 1px rgba(255, 255, 255, 0.08);
  transform: scale(1.04);
}
.play-btn:active {
  transform: scale(0.96);
}

/* Speed */
.speed-control {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0 0.5rem;
}
.speed-label {
  font-size: 0.75rem;
  color: #555;
  white-space: nowrap;
  min-width: 2.5rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.speed-slider {
  flex: 1;
  height: 3px;
  -webkit-appearance: none;
  appearance: none;
  background: transparent;
  cursor: pointer;
  outline: none;
}
.speed-slider::-webkit-slider-runnable-track {
  height: 3px;
  border-radius: 2px;
  background: rgba(255, 255, 255, 0.08);
}
.speed-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #8a8a8a;
  margin-top: -4.5px;
  transition: background 0.2s;
}
.speed-slider::-webkit-slider-thumb:hover {
  background: var(--color-accent);
}
.speed-slider::-moz-range-track {
  height: 3px;
  border-radius: 2px;
  background: rgba(255, 255, 255, 0.08);
  border: none;
}
.speed-slider::-moz-range-thumb {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #8a8a8a;
  border: none;
}
.speed-slider::-moz-range-thumb:hover {
  background: var(--color-accent);
}
.speed-input-wrap {
  display: flex;
  align-items: center;
  gap: 0.15rem;
}
.speed-input {
  width: 3.2rem;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 6px;
  color: #e8e6e3;
  font-family: inherit;
  font-size: 0.8rem;
  padding: 0.3rem;
  text-align: center;
  font-variant-numeric: tabular-nums;
  outline: none;
  -moz-appearance: textfield;
}
.speed-input::-webkit-inner-spin-button,
.speed-input::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}
.speed-input:focus {
  border-color: rgba(160, 32, 32, 0.4);
}
.speed-suffix {
  font-size: 0.75rem;
  color: #555;
}

/* Secondary actions */
.secondary-actions {
  display: flex;
  gap: 1rem;
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

/* Up Next */
.up-next-section {
  width: 100%;
  margin-top: 0.5rem;
}
.up-next-title {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 0.95rem;
  font-weight: 500;
  color: #8a8a8a;
  margin-bottom: 0.6rem;
  letter-spacing: 0.04em;
}
.up-next-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.up-next-item {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.5rem 0.85rem;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}
.up-next-item:hover {
  border-color: rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
}
.up-next-item-title {
  font-size: 0.82rem;
  color: #e8e6e3;
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.up-next-item-author {
  font-size: 0.7rem;
  color: #555;
  flex-shrink: 0;
}

/* Series */
.series-wrap {
  width: 100%;
  margin-top: 0.5rem;
}

/* Browser tips */
.browser-tip {
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 8px;
  padding: 0.85rem 1.1rem;
  font-size: 0.78rem;
  color: #555;
  width: 100%;
  line-height: 1.5;
}
.browser-tip strong {
  color: #8a8a8a;
}
.browser-tip-dismiss {
  background: none;
  border: none;
  color: #555;
  float: right;
  cursor: pointer;
  font-size: 1rem;
  padding: 0;
  margin: -0.25rem 0 0 0.5rem;
  transition: color 0.15s;
}
.browser-tip-dismiss:hover {
  color: #8a8a8a;
}
</style>
