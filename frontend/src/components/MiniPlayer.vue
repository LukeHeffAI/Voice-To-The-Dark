<script setup lang="ts">
import { computed } from 'vue'
import { usePlayerStore } from '@/stores/player'
import { usePlaylistStore } from '@/stores/playlist'
import { useRouter } from 'vue-router'

const player = usePlayerStore()
const playlist = usePlaylistStore()
const router = useRouter()

const emit = defineEmits<{ toggleDrawer: [] }>()

const progressPct = computed(() => {
  if (!player.duration) return 0
  return (player.currentTime / player.duration) * 100
})

const repeatClass = computed(() => {
  if (playlist.repeatMode === 'one') return 'repeat-active repeat-one'
  if (playlist.repeatMode === 'all') return 'repeat-active'
  return ''
})

function seekFromClick(e: MouseEvent) {
  const bar = e.currentTarget as HTMLElement
  const rect = bar.getBoundingClientRect()
  const pct = (e.clientX - rect.left) / rect.width
  player.seek(pct * player.duration)
}

function goToPlayer() {
  if (player.currentTrack) {
    router.push(`/story/${player.currentTrack.id}/play`)
  }
}
</script>

<template>
  <div v-if="player.currentTrack" class="mini-player">
    <!-- Progress bar -->
    <div class="mini-progress" @click="seekFromClick">
      <div class="mini-progress-fill" :style="{ width: progressPct + '%' }"></div>
    </div>

    <div class="mini-player-inner">
      <!-- Controls -->
      <div class="mini-controls">
        <button class="mini-btn" title="Previous" @click="playlist.prev()">&#9664;&#9664;</button>
        <button class="mini-btn play-pause" title="Play/Pause" @click="player.togglePlay()">
          <template v-if="player.isPlaying">&#10074;&#10074;</template>
          <template v-else>&#9654;</template>
        </button>
        <button class="mini-btn" title="Next" @click="playlist.next()">&#9654;&#9654;</button>
      </div>

      <!-- Track info -->
      <div class="mini-info" @click="goToPlayer">
        <div class="mini-title">{{ player.currentTrack.title }}</div>
        <div class="mini-author">
          {{ player.currentTrack.author ? 'u/' + player.currentTrack.author : 'Voice In The Dark' }}
        </div>
      </div>

      <!-- Right controls -->
      <div class="mini-right">
        <button class="mini-btn" :class="repeatClass" title="Repeat" @click="playlist.toggleRepeat()">
          &#128257;<span v-if="playlist.repeatMode === 'one'" class="text-[0.55rem] align-super font-bold">1</span>
        </button>
        <button class="mini-btn" title="Queue" @click="emit('toggleDrawer')">&#9776;</button>
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
  background: rgba(10,10,10,0.95);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-top: 1px solid var(--color-border);
  z-index: 9000;
  display: flex;
  flex-direction: column;
}
.mini-progress {
  width: 100%;
  height: 3px;
  background: rgba(255,255,255,0.06);
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
  color: var(--color-text-2);
  cursor: pointer;
  padding: 0.4rem;
  font-size: 1rem;
  transition: color 0.15s;
  -webkit-tap-highlight-color: transparent;
  line-height: 1;
}
.mini-btn:hover { color: var(--color-text-1); }
.mini-btn.play-pause { font-size: 1.2rem; color: var(--color-text-1); }
.mini-info {
  flex: 1;
  min-width: 0;
  cursor: pointer;
  padding: 0 0.5rem;
}
.mini-title {
  font-size: 0.82rem;
  font-weight: 500;
  color: var(--color-text-1);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.mini-author {
  font-size: 0.7rem;
  color: var(--color-text-3);
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
.repeat-active { color: var(--color-accent) !important; }
</style>
