<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useAuthStore } from './stores/auth'
import { usePlayerStore } from './stores/player'
import { usePlaylistStore } from './stores/playlist'
import AtmosphericEffects from './components/AtmosphericEffects.vue'
import ToastNotifications from './components/ToastNotifications.vue'
import MiniPlayer from './components/MiniPlayer.vue'
import PlaylistDrawer from './components/PlaylistDrawer.vue'

const auth = useAuthStore()
const player = usePlayerStore()
const playlist = usePlaylistStore()

const audioEl = ref<HTMLAudioElement>()
const drawerOpen = ref(false)

onMounted(async () => {
  // Wire audio element to player store
  if (audioEl.value) {
    player.setAudioElement(audioEl.value)
  }

  // Initialize playlist auto-advance
  playlist.initAutoAdvance()

  // Restore auth session
  await auth.init()
})

function toggleDrawer() {
  drawerOpen.value = !drawerOpen.value
}
</script>

<template>
  <div class="min-h-screen bg-bg text-white font-sans" :class="{ 'pb-16': player.storyId }">
    <!-- Navigation -->
    <nav class="nav-bar">
      <div class="nav-inner">
        <RouterLink to="/" class="nav-logo">VTTD</RouterLink>
        <div class="nav-links">
          <RouterLink to="/">Stories</RouterLink>
          <RouterLink to="/submit">Submit</RouterLink>
          <RouterLink to="/settings">Settings</RouterLink>
        </div>
        <div class="nav-auth">
          <template v-if="auth.isAuthenticated">
            <span class="nav-username">{{ auth.user?.username }}</span>
            <button class="nav-link-btn" @click="auth.logout()">Logout</button>
          </template>
          <RouterLink v-else to="/login">Sign in</RouterLink>
        </div>
      </div>
    </nav>

    <!-- Page content -->
    <main class="page-content">
      <RouterView />
    </main>

    <!-- Persistent audio element -->
    <audio ref="audioEl" />

    <!-- Mini-player bar -->
    <MiniPlayer @toggle-drawer="toggleDrawer" />

    <!-- Playlist drawer -->
    <PlaylistDrawer :open="drawerOpen" @close="drawerOpen = false" />

    <!-- Toast notifications -->
    <ToastNotifications />

    <!-- Atmospheric effects -->
    <AtmosphericEffects />
  </div>
</template>

<style scoped>
.nav-bar {
  position: sticky;
  top: 0;
  z-index: 100;
  background: rgba(5, 5, 5, 0.85);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.nav-inner {
  max-width: 960px;
  margin: 0 auto;
  padding: 0 1rem;
  height: 48px;
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.nav-logo {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--color-accent);
  text-decoration: none;
  letter-spacing: 0.08em;
}

.nav-links {
  display: flex;
  gap: 1rem;
  flex: 1;
}
.nav-links a {
  color: #555;
  text-decoration: none;
  font-size: 0.8rem;
  letter-spacing: 0.02em;
  transition: color 0.2s;
}
.nav-links a:hover,
.nav-links a.router-link-active {
  color: #8a8a8a;
}

.nav-auth {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.8rem;
}
.nav-auth a {
  color: #555;
  text-decoration: none;
  transition: color 0.2s;
}
.nav-auth a:hover {
  color: #8a8a8a;
}
.nav-username {
  color: #8a8a8a;
  font-weight: 500;
}
.nav-link-btn {
  background: none;
  border: none;
  color: #555;
  cursor: pointer;
  font-size: 0.8rem;
  padding: 0;
  transition: color 0.2s;
}
.nav-link-btn:hover {
  color: #8a8a8a;
}

.page-content {
  max-width: 960px;
  margin: 0 auto;
  padding: 1.5rem 1rem;
  position: relative;
  z-index: 3;
}
</style>
