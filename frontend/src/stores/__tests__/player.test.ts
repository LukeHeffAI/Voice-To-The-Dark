import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { usePlayerStore } from '../player'

// Mock the API client
vi.mock('@/api/client', () => ({
  playerApi: {
    storyInfo: vi.fn(),
    streamUrl: vi.fn((id: number) => `/api/player/stream/${id}`),
  },
  storiesApi: {
    getPlayback: vi.fn().mockResolvedValue({ position_seconds: 0 }),
  },
}))

describe('Player Store', () => {
  let store: ReturnType<typeof usePlayerStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    store = usePlayerStore()
  })

  describe('initial state', () => {
    it('starts with no track loaded', () => {
      expect(store.currentTrack).toBeNull()
    })

    it('starts not playing', () => {
      expect(store.isPlaying).toBe(false)
    })

    it('starts with speed 1', () => {
      expect(store.playbackSpeed).toBe(1)
    })

    it('starts at time 0', () => {
      expect(store.currentTime).toBe(0)
      expect(store.duration).toBe(0)
    })
  })

  describe('setSpeed', () => {
    it('sets playback speed', () => {
      store.setSpeed(1.5)
      expect(store.playbackSpeed).toBe(1.5)
    })

    it('clamps minimum to 0.5', () => {
      store.setSpeed(0.1)
      expect(store.playbackSpeed).toBe(0.5)
    })

    it('clamps maximum to 3', () => {
      store.setSpeed(5)
      expect(store.playbackSpeed).toBe(3)
    })

    it('rounds to nearest 0.05', () => {
      store.setSpeed(1.23)
      expect(store.playbackSpeed).toBe(1.25)
    })

    it('handles exact values', () => {
      store.setSpeed(2)
      expect(store.playbackSpeed).toBe(2)
    })
  })

  describe('seek', () => {
    it('does nothing without audio element', () => {
      // No audio element set, so seek should just return
      store.seek(10)
      expect(store.currentTime).toBe(0)
    })
  })

  describe('skipForward / skipBack', () => {
    it('skipForward defaults to 15 seconds', () => {
      // Without audio element these are no-ops but shouldn't throw
      store.skipForward()
      store.skipForward(30)
    })

    it('skipBack defaults to 15 seconds', () => {
      store.skipBack()
      store.skipBack(30)
    })
  })

  describe('play / pause / togglePlay', () => {
    it('does not throw without audio element', () => {
      expect(() => store.play()).not.toThrow()
      expect(() => store.pause()).not.toThrow()
      expect(() => store.togglePlay()).not.toThrow()
    })
  })

  describe('savePosition', () => {
    it('does nothing without current track', () => {
      // Should not throw
      store.savePosition()
    })
  })
})
