<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { usePlayerStore } from '../stores/player'
import { usePlaylistStore } from '../stores/playlist'
import { formatTime } from '../composables/useFormatTime'

const player = usePlayerStore()
const playlist = usePlaylistStore()
const router = useRouter()

const emit = defineEmits<{ toggleDrawer: [] }>()

const progressPercent = computed(() => {
  if (!player.duration || player.duration <= 0) return 0
  return (player.currentTime / player.duration) * 100
})

const repeatIcon = computed(() => {
  if (playlist.repeatMode === 'one') return '🔂'
  return '🔁'
})

const repeatClass = computed(() => {
  if (playlist.repeatMode === 'off') return ''
  return 'repeat-active'
})

function seekFromProgress(e: MouseEvent) {
  const target = e.currentTarget as HTMLElement
  const rect = target.getBoundingClientRect()
  const pct = (e.clientX - rect.left) / rect.width
  player.seek(pct * player.duration)
}

function goToPlayer() {
  if (player.storyId) {
    router.push({ name: 'player', params: { id: player.storyId } })
  }
}

const timeDisplay = computed(() => {
  return `${formatTime(player.currentTime)} / ${formatTime(player.duration)}`
})
</script>

<template>
  <div v-if="player.storyId" class="mini-player">
    <!-- Progress bar -->
    <div class="mini-progress" @click="seekFromProgress">
      <div class="mini-progress-fill" :style="{ width: progressPercent + '%' }" />
    </div>

    <div class="mini-player-inner">
      <!-- Play/pause -->
      <div class="mini-controls">
        <button class="mini-btn play-pause" @click="player.togglePlay()">
          {{ player.isPlaying ? '⏸' : '▶' }}
        </button>
      </div>

      <!-- Track info -->
      <div class="mini-info" @click="goToPlayer">
        <div class="mini-title">{{ player.title || 'No track loaded' }}</div>
        <div class="mini-author">
          {{ player.author ? `by ${player.author}` : timeDisplay }}
        </div>
      </div>

      <!-- Right controls -->
      <div class="mini-right">
        <button class="mini-btn" :class="repeatClass" @click="playlist.toggleRepeat()">
          {{ repeatIcon }}
        </button>
        <button class="mini-btn" @click="emit('toggleDrawer')">📋</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mini-player {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 56px;
  background: rgba(10, 10, 10, 0.95);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  z-index: 9000;
  display: flex;
  flex-direction: column;
}

.mini-progress {
  width: 100%;
  height: 3px;
  background: rgba(255, 255, 255, 0.06);
  cursor: pointer;
  flex-shrink: 0;
}
.mini-progress-fill {
  height: 100%;
  background: var(--color-accent);
  transition: width 0.3s linear;
  pointer-events: none;
}

.mini-player-inner {
  flex: 1;
  display: flex;
  align-items: center;
  padding: 0 0.75rem;
  gap: 0.5rem;
}

.mini-controls {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  flex-shrink: 0;
}

.mini-btn {
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.4);
  cursor: pointer;
  padding: 0.4rem;
  font-size: 1rem;
  transition: color 0.15s;
  -webkit-tap-highlight-color: transparent;
  line-height: 1;
}
.mini-btn:hover {
  color: rgba(255, 255, 255, 0.8);
}
.mini-btn.play-pause {
  font-size: 1.2rem;
  color: #e8e6e3;
}
.mini-btn.repeat-active {
  color: var(--color-accent);
}

.mini-info {
  flex: 1;
  min-width: 0;
  cursor: pointer;
  padding: 0 0.5rem;
}
.mini-title {
  font-size: 0.82rem;
  font-weight: 500;
  color: #e8e6e3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.mini-author {
  font-size: 0.7rem;
  color: #555;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mini-right {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  flex-shrink: 0;
}
</style>
