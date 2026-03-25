<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { usePlayerStore } from '@/stores/player'
import { usePlaylistStore } from '@/stores/playlist'
import { useAuthStore } from '@/stores/auth'
import FogOverlay from '@/components/FogOverlay.vue'
import AppNav from '@/components/AppNav.vue'
import MiniPlayer from '@/components/MiniPlayer.vue'
import PlaylistDrawer from '@/components/PlaylistDrawer.vue'
import ToastContainer from '@/components/ToastContainer.vue'

const player = usePlayerStore()
const playlist = usePlaylistStore()
const auth = useAuthStore()

const audioEl = ref<HTMLAudioElement>()
const drawerOpen = ref(false)

onMounted(async () => {
  // Bind audio element to player store
  if (audioEl.value) {
    player.setAudioElement(audioEl.value)
  }

  // Wire up track-ended → playlist auto-advance
  audioEl.value?.addEventListener('ended', () => {
    playlist.onTrackEnded()
  })

  // Validate token on app load
  if (auth.token) {
    await auth.fetchMe()
  }
})

// Toggle body class for mini-player padding
watch(
  () => player.currentTrack,
  (track) => {
    document.body.classList.toggle('has-miniplayer', !!track)
  },
  { immediate: true },
)

function toggleDrawer() {
  drawerOpen.value = !drawerOpen.value
}
</script>

<template>
  <div class="min-h-screen">
    <FogOverlay />
    <AppNav />

    <RouterView />

    <!-- Persistent audio element -->
    <audio ref="audioEl" preload="none" playsinline></audio>

    <!-- Mini player & playlist drawer -->
    <MiniPlayer @toggle-drawer="toggleDrawer" />
    <PlaylistDrawer :open="drawerOpen" @close="drawerOpen = false" />

    <ToastContainer />
  </div>
</template>
