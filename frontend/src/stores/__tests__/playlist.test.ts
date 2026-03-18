import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { usePlaylistStore } from '../playlist'
import type { TrackInfo } from '../../api/types'

// Mock the player store used by playlist for playAt/next/prev
vi.mock('../player', () => ({
  usePlayerStore: () => ({
    loadTrack: vi.fn(),
    seek: vi.fn(),
    play: vi.fn(),
    currentTime: 0,
    onEnded: vi.fn(),
  }),
}))

function track(id: number): TrackInfo {
  return { storyId: id, title: `Story ${id}`, author: `Author ${id}` }
}

describe('usePlaylistStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  // --- addNext ---
  describe('addNext', () => {
    it('inserts after current index', () => {
      const store = usePlaylistStore()
      store.addToEnd(track(1))
      store.addToEnd(track(2))
      store.currentIndex = 0

      store.addNext(track(99))

      expect(store.items[1]!.storyId).toBe(99)
      expect(store.items).toHaveLength(3)
    })

    it('inserts at position 1 when queue has one item at index 0', () => {
      const store = usePlaylistStore()
      store.addToEnd(track(1))

      store.addNext(track(2))

      expect(store.items[0]!.storyId).toBe(1)
      expect(store.items[1]!.storyId).toBe(2)
    })
  })

  // --- addToEnd ---
  describe('addToEnd', () => {
    it('appends to the queue', () => {
      const store = usePlaylistStore()
      store.addToEnd(track(1))
      store.addToEnd(track(2))
      store.addToEnd(track(3))

      expect(store.items).toHaveLength(3)
      expect(store.items[2]!.storyId).toBe(3)
    })
  })

  // --- removeAt ---
  describe('removeAt', () => {
    it('removes item at the given index', () => {
      const store = usePlaylistStore()
      store.addToEnd(track(1))
      store.addToEnd(track(2))
      store.addToEnd(track(3))

      store.removeAt(1)

      expect(store.items).toHaveLength(2)
      expect(store.items[1]!.storyId).toBe(3)
    })

    it('decrements currentIndex when removing before it', () => {
      const store = usePlaylistStore()
      store.addToEnd(track(1))
      store.addToEnd(track(2))
      store.addToEnd(track(3))
      store.currentIndex = 2

      store.removeAt(0)

      expect(store.currentIndex).toBe(1)
    })

    it('clamps currentIndex when removing last item at current', () => {
      const store = usePlaylistStore()
      store.addToEnd(track(1))
      store.addToEnd(track(2))
      store.currentIndex = 1

      store.removeAt(1)

      expect(store.currentIndex).toBe(0)
    })

    it('resets to 0 when queue becomes empty', () => {
      const store = usePlaylistStore()
      store.addToEnd(track(1))
      store.currentIndex = 0

      store.removeAt(0)

      expect(store.items).toHaveLength(0)
      expect(store.currentIndex).toBe(0)
    })

    it('ignores out-of-bounds index', () => {
      const store = usePlaylistStore()
      store.addToEnd(track(1))

      store.removeAt(-1)
      store.removeAt(5)

      expect(store.items).toHaveLength(1)
    })
  })

  // --- reorder ---
  describe('reorder', () => {
    it('moves item from old to new position', () => {
      const store = usePlaylistStore()
      store.addToEnd(track(1))
      store.addToEnd(track(2))
      store.addToEnd(track(3))

      store.reorder(0, 2)

      expect(store.items[0]!.storyId).toBe(2)
      expect(store.items[1]!.storyId).toBe(3)
      expect(store.items[2]!.storyId).toBe(1)
    })

    it('adjusts currentIndex when the playing track is moved', () => {
      const store = usePlaylistStore()
      store.addToEnd(track(1))
      store.addToEnd(track(2))
      store.addToEnd(track(3))
      store.currentIndex = 0

      store.reorder(0, 2)

      expect(store.currentIndex).toBe(2)
    })

    it('decrements currentIndex when item moves from before to after current', () => {
      const store = usePlaylistStore()
      store.addToEnd(track(1))
      store.addToEnd(track(2))
      store.addToEnd(track(3))
      store.currentIndex = 1

      store.reorder(0, 2)

      expect(store.currentIndex).toBe(0)
    })

    it('increments currentIndex when item moves from after to before current', () => {
      const store = usePlaylistStore()
      store.addToEnd(track(1))
      store.addToEnd(track(2))
      store.addToEnd(track(3))
      store.currentIndex = 1

      store.reorder(2, 0)

      expect(store.currentIndex).toBe(2)
    })

    it('does nothing when old equals new', () => {
      const store = usePlaylistStore()
      store.addToEnd(track(1))
      store.addToEnd(track(2))
      store.currentIndex = 0

      store.reorder(0, 0)

      expect(store.items[0]!.storyId).toBe(1)
      expect(store.currentIndex).toBe(0)
    })
  })

  // --- toggleRepeat ---
  describe('toggleRepeat', () => {
    it('cycles off → all → one → off', () => {
      const store = usePlaylistStore()
      expect(store.repeatMode).toBe('off')

      store.toggleRepeat()
      expect(store.repeatMode).toBe('all')

      store.toggleRepeat()
      expect(store.repeatMode).toBe('one')

      store.toggleRepeat()
      expect(store.repeatMode).toBe('off')
    })
  })

  // --- clear ---
  describe('clear', () => {
    it('empties the queue and resets index', () => {
      const store = usePlaylistStore()
      store.addToEnd(track(1))
      store.addToEnd(track(2))
      store.currentIndex = 1

      store.clear()

      expect(store.items).toHaveLength(0)
      expect(store.currentIndex).toBe(0)
    })
  })

  // --- next ---
  describe('next', () => {
    it('advances to the next track', () => {
      const store = usePlaylistStore()
      store.addToEnd(track(1))
      store.addToEnd(track(2))
      store.currentIndex = 0

      store.next()

      expect(store.currentIndex).toBe(1)
    })

    it('does not advance past the end when repeat is off', () => {
      const store = usePlaylistStore()
      store.addToEnd(track(1))
      store.currentIndex = 0
      store.repeatMode = 'off'

      store.next()

      expect(store.currentIndex).toBe(0)
    })

    it('wraps to 0 when repeat is "all" and at end', () => {
      const store = usePlaylistStore()
      store.addToEnd(track(1))
      store.addToEnd(track(2))
      store.currentIndex = 1
      store.repeatMode = 'all'

      store.next()

      expect(store.currentIndex).toBe(0)
    })

    it('does nothing on empty queue', () => {
      const store = usePlaylistStore()
      store.next()
      expect(store.currentIndex).toBe(0)
    })
  })

  // --- prev ---
  describe('prev', () => {
    it('goes to previous track when currentTime <= 3', () => {
      const store = usePlaylistStore()
      store.addToEnd(track(1))
      store.addToEnd(track(2))
      store.currentIndex = 1

      store.prev()

      expect(store.currentIndex).toBe(0)
    })

    it('wraps to last when repeat is "all" and at start', () => {
      const store = usePlaylistStore()
      store.addToEnd(track(1))
      store.addToEnd(track(2))
      store.currentIndex = 0
      store.repeatMode = 'all'

      store.prev()

      expect(store.currentIndex).toBe(1)
    })
  })

  // --- getCurrentTrack ---
  describe('getCurrentTrack', () => {
    it('returns the current track', () => {
      const store = usePlaylistStore()
      store.addToEnd(track(42))

      expect(store.getCurrentTrack()?.storyId).toBe(42)
    })

    it('returns null on empty queue', () => {
      const store = usePlaylistStore()
      expect(store.getCurrentTrack()).toBeNull()
    })
  })
})
