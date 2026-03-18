import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { playerApi, storiesApi } from '@/api/client'
import type { StoryInfo } from '@/types'

export const usePlayerStore = defineStore(
  'player',
  () => {
    // ── State ────────────────────────────────────────
    const currentTrack = ref<StoryInfo | null>(null)
    const isPlaying = ref(false)
    const currentTime = ref(0)
    const duration = ref(0)
    const playbackSpeed = ref(1)
    const isLoading = ref(false)

    let audioEl: HTMLAudioElement | null = null
    let saveTimer: ReturnType<typeof setInterval> | null = null
    let visibilityHandler: (() => void) | null = null
    let beforeUnloadHandler: (() => void) | null = null

    // ── Audio element binding ────────────────────────
    function setAudioElement(el: HTMLAudioElement) {
      // Clean up previous global listeners to prevent leaks on re-mount / HMR
      if (visibilityHandler) document.removeEventListener('visibilitychange', visibilityHandler)
      if (beforeUnloadHandler) window.removeEventListener('beforeunload', beforeUnloadHandler)

      audioEl = el

      audioEl.addEventListener('play', () => {
        isPlaying.value = true
        if ('mediaSession' in navigator) navigator.mediaSession.playbackState = 'playing'
        startAutoSave()
      })

      audioEl.addEventListener('pause', () => {
        isPlaying.value = false
        if ('mediaSession' in navigator) navigator.mediaSession.playbackState = 'paused'
        savePosition()
        stopAutoSave()
      })

      audioEl.addEventListener('timeupdate', () => {
        if (audioEl) {
          currentTime.value = audioEl.currentTime
          duration.value = audioEl.duration || 0
          updatePositionState()
        }
      })

      audioEl.addEventListener('loadedmetadata', () => {
        if (audioEl) {
          duration.value = audioEl.duration || 0
          isLoading.value = false
        }
      })

      audioEl.addEventListener('ended', () => {
        isPlaying.value = false
        savePosition()
        stopAutoSave()
      })

      audioEl.addEventListener('waiting', () => {
        isLoading.value = true
      })

      audioEl.addEventListener('canplay', () => {
        isLoading.value = false
      })

      // Save position on visibility change and before unload
      visibilityHandler = () => {
        if (document.visibilityState === 'hidden') savePosition()
      }
      beforeUnloadHandler = () => savePosition()
      document.addEventListener('visibilitychange', visibilityHandler)
      window.addEventListener('beforeunload', beforeUnloadHandler)

      // Restore track info from localStorage (don't auto-load audio)
      try {
        const saved = localStorage.getItem('vttd_current_track')
        if (saved) {
          const parsed = JSON.parse(saved) as StoryInfo
          if (parsed?.id) {
            currentTrack.value = parsed
          }
        }
      } catch {
        /* ignore */
      }
    }

    // ── Track loading ────────────────────────────────
    async function loadTrack(storyId: number, autoplay = true) {
      if (!audioEl) return

      // If already playing this track, just resume
      if (currentTrack.value?.id === storyId && audioEl.src) {
        if (autoplay && audioEl.paused) audioEl.play().catch(() => {})
        return
      }

      // Save position of previous track
      savePosition()
      isLoading.value = true

      // Fetch story info
      try {
        const info = await playerApi.storyInfo(storyId)
        currentTrack.value = info

        // Persist for page-reload recovery
        localStorage.setItem('vttd_current_track', JSON.stringify(info))

        // Set source and load
        audioEl.src = playerApi.streamUrl(storyId)
        audioEl.load()

        // Restore playback speed
        audioEl.playbackRate = playbackSpeed.value

        // Fetch resume position
        try {
          const pb = await storiesApi.getPlayback(storyId)
          if (pb.position_seconds > 0 && currentTrack.value?.id === storyId) {
            audioEl.currentTime = pb.position_seconds
          }
        } catch {
          /* no saved position */
        }

        if (autoplay) audioEl.play().catch(() => {})
        setupMediaSession()
      } catch {
        isLoading.value = false
      }
    }

    // ── Playback controls ────────────────────────────
    function play() {
      audioEl?.play().catch(() => {})
    }

    function pause() {
      audioEl?.pause()
    }

    function togglePlay() {
      if (!audioEl) return
      if (audioEl.paused) play()
      else pause()
    }

    function seek(time: number) {
      if (!audioEl) return
      audioEl.currentTime = Math.max(0, Math.min(time, audioEl.duration || 0))
      updatePositionState()
    }

    function skipForward(seconds = 15) {
      if (audioEl) seek(audioEl.currentTime + seconds)
    }

    function skipBack(seconds = 15) {
      if (audioEl) seek(audioEl.currentTime - seconds)
    }

    function setSpeed(rate: number) {
      rate = Math.max(0.5, Math.min(3, rate))
      rate = Math.round(rate * 20) / 20
      playbackSpeed.value = rate
      if (audioEl) audioEl.playbackRate = rate
      updatePositionState()
    }

    // ── Position saving ──────────────────────────────
    function savePosition() {
      if (!currentTrack.value) return
      if (!audioEl || audioEl.currentTime < 1) return
      const body = JSON.stringify({
        story_id: currentTrack.value.id,
        position_seconds: Math.floor(audioEl.currentTime),
      })
      try {
        const headers: Record<string, string> = { 'Content-Type': 'application/json' }
        try {
          const raw = localStorage.getItem('auth')
          if (raw) {
            const parsed = JSON.parse(raw)
            if (parsed?.token) headers['Authorization'] = `Bearer ${parsed.token}`
          }
        } catch { /* ignore */ }
        fetch('/api/stories/playback', {
          method: 'POST',
          headers,
          body,
          keepalive: true,
        }).catch(() => { /* ignore */ })
      } catch {
        /* ignore */
      }
    }

    function startAutoSave() {
      stopAutoSave()
      saveTimer = setInterval(() => savePosition(), 15000)
    }

    function stopAutoSave() {
      if (saveTimer) {
        clearInterval(saveTimer)
        saveTimer = null
      }
    }

    // ── MediaSession ─────────────────────────────────
    function setupMediaSession() {
      if (!('mediaSession' in navigator) || !currentTrack.value) return

      navigator.mediaSession.metadata = new MediaMetadata({
        title: currentTrack.value.title,
        artist: 'Voice In The Dark',
        album: 'NoSleep Narrations',
        artwork: [
          { src: '/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icon-512.png', sizes: '512x512', type: 'image/png' },
        ],
      })

      const handlers: [MediaSessionAction, MediaSessionActionHandler][] = [
        ['play', () => play()],
        ['pause', () => pause()],
        ['seekbackward', (d) => skipBack(d.seekOffset || 15)],
        ['seekforward', (d) => skipForward(d.seekOffset || 15)],
        [
          'seekto',
          (d) => {
            if (d.seekTime !== undefined) seek(d.seekTime)
          },
        ],
        [
          'stop',
          () => {
            pause()
            seek(0)
            savePosition()
          },
        ],
      ]

      for (const [action, handler] of handlers) {
        try {
          navigator.mediaSession.setActionHandler(action, handler)
        } catch {
          /* unsupported action */
        }
      }
    }

    function updatePositionState() {
      if (!('mediaSession' in navigator) || !audioEl) return
      if (!isFinite(audioEl.duration) || audioEl.duration <= 0) return
      try {
        navigator.mediaSession.setPositionState({
          duration: audioEl.duration,
          playbackRate: audioEl.playbackRate,
          position: Math.min(audioEl.currentTime, audioEl.duration),
        })
      } catch {
        /* ignore */
      }
    }

    // Sync speed changes to persisted state
    watch(playbackSpeed, (rate) => {
      if (audioEl) audioEl.playbackRate = rate
    })

    return {
      currentTrack,
      isPlaying,
      currentTime,
      duration,
      playbackSpeed,
      isLoading,
      setAudioElement,
      loadTrack,
      play,
      pause,
      togglePlay,
      seek,
      skipForward,
      skipBack,
      setSpeed,
      savePosition,
      setupMediaSession,
    }
  },
  {
    persist: {
      pick: ['playbackSpeed'],
    },
  },
)
