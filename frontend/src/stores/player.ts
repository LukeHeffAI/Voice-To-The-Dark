import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { streamUrl } from '../api/player'
import { getPlayback } from '../api/stories'

export const usePlayerStore = defineStore(
  'player',
  () => {
    // ── State ──────────────────────────────────────────
    const storyId = ref<number | null>(null)
    const title = ref('')
    const author = ref('')
    const isPlaying = ref(false)
    const currentTime = ref(0)
    const duration = ref(0)
    const playbackSpeed = ref(1)

    // Audio element ref — set by App.vue on mount
    let audioEl: HTMLAudioElement | null = null
    let saveTimer: ReturnType<typeof setInterval> | null = null

    // ── Audio element wiring ───────────────────────────

    function setAudioElement(el: HTMLAudioElement) {
      audioEl = el

      el.addEventListener('play', () => {
        isPlaying.value = true
        if ('mediaSession' in navigator) navigator.mediaSession.playbackState = 'playing'
        startAutoSave()
      })

      el.addEventListener('pause', () => {
        isPlaying.value = false
        if ('mediaSession' in navigator) navigator.mediaSession.playbackState = 'paused'
        savePosition()
        stopAutoSave()
      })

      el.addEventListener('timeupdate', () => {
        currentTime.value = el.currentTime
        duration.value = el.duration || 0
        updatePositionState()
      })

      el.addEventListener('loadedmetadata', () => {
        duration.value = el.duration || 0
      })

      el.addEventListener('ended', () => {
        isPlaying.value = false
        savePosition()
        stopAutoSave()
        // Playlist store listens to this via watch on isPlaying + ended detection
      })

      // Save on visibility change and before unload
      document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'hidden') savePosition()
      })
      window.addEventListener('beforeunload', () => savePosition())

      // Restore speed
      const savedSpeed = parseFloat(localStorage.getItem('vttd_playback_speed') || '1')
      if (savedSpeed >= 0.5 && savedSpeed <= 3) {
        playbackSpeed.value = savedSpeed
        el.playbackRate = savedSpeed
      }
    }

    // ── Track loading ──────────────────────────────────

    async function loadTrack(
      newStoryId: number,
      newTitle: string,
      newAuthor: string,
      autoplay = false,
    ) {
      if (!audioEl) return

      // If already playing this track, just sync UI
      if (storyId.value === newStoryId && audioEl.src.includes(`/stream/${newStoryId}`)) {
        if (autoplay && audioEl.paused) {
          audioEl.play().catch(() => {})
        }
        return
      }

      // Save position of previous track
      savePosition()

      storyId.value = newStoryId
      title.value = newTitle || ''
      author.value = newAuthor || ''

      // Set source and load
      audioEl.src = streamUrl(newStoryId)
      audioEl.load()

      // Apply speed
      audioEl.playbackRate = playbackSpeed.value

      // Fetch resume position
      try {
        const state = await getPlayback(newStoryId)
        if (state.position_seconds > 0 && storyId.value === newStoryId) {
          audioEl.currentTime = state.position_seconds
        }
      } catch {
        // No saved position
      }

      if (autoplay) {
        audioEl.play().catch(() => {})
      }

      setupMediaSession()
    }

    // ── Playback controls ──────────────────────────────

    function play() {
      audioEl?.play().catch(() => {})
    }

    function pause() {
      audioEl?.pause()
    }

    function togglePlay() {
      if (audioEl?.paused) play()
      else pause()
    }

    function seek(time: number) {
      if (!audioEl) return
      audioEl.currentTime = Math.max(0, Math.min(time, audioEl.duration || 0))
      updatePositionState()
    }

    function skip(seconds: number) {
      if (!audioEl) return
      seek(audioEl.currentTime + seconds)
    }

    function setSpeed(rate: number) {
      rate = Math.max(0.5, Math.min(3, rate))
      rate = Math.round(rate * 20) / 20
      playbackSpeed.value = rate
      if (audioEl) audioEl.playbackRate = rate
      localStorage.setItem('vttd_playback_speed', String(rate))
      updatePositionState()
    }

    // ── Position saving ────────────────────────────────

    function savePosition() {
      if (!storyId.value || !audioEl) return
      if (!audioEl.currentTime || audioEl.currentTime < 1) return
      try {
        navigator.sendBeacon(
          '/api/stories/playback',
          new Blob(
            [
              JSON.stringify({
                story_id: storyId.value,
                position_seconds: Math.floor(audioEl.currentTime),
              }),
            ],
            { type: 'application/json' },
          ),
        )
      } catch {
        // Beacon unavailable
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

    // ── MediaSession ───────────────────────────────────

    function setupMediaSession() {
      if (!('mediaSession' in navigator)) return

      navigator.mediaSession.metadata = new MediaMetadata({
        title: title.value,
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
        ['seekbackward', (d) => skip(-(d.seekOffset || 15))],
        ['seekforward', (d) => skip(d.seekOffset || 15)],
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
            if (audioEl) audioEl.currentTime = 0
            savePosition()
          },
        ],
      ]

      for (const [action, handler] of handlers) {
        try {
          navigator.mediaSession.setActionHandler(action, handler)
        } catch {
          // Handler not supported
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
        // Position state not supported
      }
    }

    /** Detect track end for playlist auto-advance. */
    function onEnded(callback: () => void) {
      watch(isPlaying, (playing, wasPaying) => {
        if (wasPaying && !playing && audioEl && audioEl.ended) {
          callback()
        }
      })
    }

    return {
      storyId,
      title,
      author,
      isPlaying,
      currentTime,
      duration,
      playbackSpeed,
      setAudioElement,
      loadTrack,
      play,
      pause,
      togglePlay,
      seek,
      skip,
      setSpeed,
      savePosition,
      onEnded,
    }
  },
  {
    persist: {
      pick: ['storyId', 'title', 'author', 'playbackSpeed'],
    },
  },
)
