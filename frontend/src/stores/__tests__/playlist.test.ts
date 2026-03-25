import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { usePlaylistStore } from '../playlist'
import type { PlaylistItem } from '@/types'

// Mock the player store to avoid side effects
vi.mock('../player', () => ({
  usePlayerStore: () => ({
    loadTrack: vi.fn(),
    seek: vi.fn(),
    play: vi.fn(),
    currentTime: 0,
  }),
}))

function makeItem(id: number, title = `Story ${id}`): PlaylistItem {
  return { storyId: id, title, author: '' }
}

describe('Playlist Store', () => {
  let store: ReturnType<typeof usePlaylistStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    store = usePlaylistStore()
  })

  describe('addToEnd', () => {
    it('appends item to empty list', () => {
      store.addToEnd(makeItem(1))
      expect(store.items).toHaveLength(1)
      expect(store.items[0].storyId).toBe(1)
    })

    it('appends multiple items in order', () => {
      store.addToEnd(makeItem(1))
      store.addToEnd(makeItem(2))
      store.addToEnd(makeItem(3))
      expect(store.items.map((i) => i.storyId)).toEqual([1, 2, 3])
    })
  })

  describe('addNext', () => {
    it('inserts after current index', () => {
      store.addToEnd(makeItem(1))
      store.addToEnd(makeItem(3))
      store.currentIndex = 0
      store.addNext(makeItem(2))
      expect(store.items.map((i) => i.storyId)).toEqual([1, 2, 3])
    })

    it('inserts at index 1 when current is 0', () => {
      store.addToEnd(makeItem(1))
      store.addNext(makeItem(2))
      expect(store.items[1].storyId).toBe(2)
    })
  })

  describe('removeAt', () => {
    beforeEach(() => {
      store.addToEnd(makeItem(1))
      store.addToEnd(makeItem(2))
      store.addToEnd(makeItem(3))
    })

    it('removes item at index', () => {
      store.removeAt(1)
      expect(store.items.map((i) => i.storyId)).toEqual([1, 3])
    })

    it('decrements currentIndex when removing before it', () => {
      store.currentIndex = 2
      store.removeAt(0)
      expect(store.currentIndex).toBe(1)
    })

    it('does not change currentIndex when removing after it', () => {
      store.currentIndex = 0
      store.removeAt(2)
      expect(store.currentIndex).toBe(0)
    })

    it('clamps currentIndex when removing last item at current', () => {
      store.currentIndex = 2
      store.removeAt(2)
      expect(store.currentIndex).toBe(1)
    })

    it('resets to 0 when removing the only item', () => {
      store.items = [makeItem(1)]
      store.currentIndex = 0
      store.removeAt(0)
      expect(store.currentIndex).toBe(0)
      expect(store.items).toHaveLength(0)
    })

    it('ignores invalid index', () => {
      store.removeAt(-1)
      store.removeAt(99)
      expect(store.items).toHaveLength(3)
    })
  })

  describe('reorder', () => {
    beforeEach(() => {
      store.addToEnd(makeItem(1))
      store.addToEnd(makeItem(2))
      store.addToEnd(makeItem(3))
    })

    it('moves item forward', () => {
      store.reorder(0, 2)
      expect(store.items.map((i) => i.storyId)).toEqual([2, 3, 1])
    })

    it('moves item backward', () => {
      store.reorder(2, 0)
      expect(store.items.map((i) => i.storyId)).toEqual([3, 1, 2])
    })

    it('follows currentIndex when moving current item', () => {
      store.currentIndex = 0
      store.reorder(0, 2)
      expect(store.currentIndex).toBe(2)
    })

    it('adjusts currentIndex when item moves past it', () => {
      store.currentIndex = 1
      store.reorder(0, 2)
      expect(store.currentIndex).toBe(0)
    })

    it('does nothing for same index', () => {
      store.reorder(1, 1)
      expect(store.items.map((i) => i.storyId)).toEqual([1, 2, 3])
    })

    it('ignores invalid indices', () => {
      store.reorder(-1, 1)
      store.reorder(1, 99)
      expect(store.items.map((i) => i.storyId)).toEqual([1, 2, 3])
    })
  })

  describe('clear', () => {
    it('empties list and resets index', () => {
      store.addToEnd(makeItem(1))
      store.addToEnd(makeItem(2))
      store.currentIndex = 1
      store.clear()
      expect(store.items).toHaveLength(0)
      expect(store.currentIndex).toBe(0)
    })
  })

  describe('toggleRepeat', () => {
    it('cycles off → all → one → off', () => {
      expect(store.repeatMode).toBe('off')
      store.toggleRepeat()
      expect(store.repeatMode).toBe('all')
      store.toggleRepeat()
      expect(store.repeatMode).toBe('one')
      store.toggleRepeat()
      expect(store.repeatMode).toBe('off')
    })
  })

  describe('ensureCurrent', () => {
    it('adds item to front if playlist is empty', () => {
      store.ensureCurrent(makeItem(5))
      expect(store.items).toHaveLength(1)
      expect(store.items[0].storyId).toBe(5)
      expect(store.currentIndex).toBe(0)
    })

    it('finds existing item and sets currentIndex', () => {
      store.addToEnd(makeItem(1))
      store.addToEnd(makeItem(2))
      store.addToEnd(makeItem(3))
      store.currentIndex = 0
      store.ensureCurrent(makeItem(3))
      expect(store.currentIndex).toBe(2)
    })

    it('does nothing if item is already current', () => {
      store.addToEnd(makeItem(1))
      store.currentIndex = 0
      store.ensureCurrent(makeItem(1))
      expect(store.items).toHaveLength(1)
      expect(store.currentIndex).toBe(0)
    })
  })

  describe('next', () => {
    it('does nothing on empty playlist', () => {
      store.next()
      expect(store.currentIndex).toBe(0)
    })

    it('does not advance past end with repeat off', () => {
      store.addToEnd(makeItem(1))
      store.currentIndex = 0
      store.next()
      expect(store.currentIndex).toBe(0)
    })
  })

  describe('onTrackEnded', () => {
    it('advances to next track', () => {
      store.addToEnd(makeItem(1))
      store.addToEnd(makeItem(2))
      store.currentIndex = 0
      store.onTrackEnded()
      expect(store.currentIndex).toBe(1)
    })

    it('wraps to beginning with repeat all', () => {
      store.addToEnd(makeItem(1))
      store.addToEnd(makeItem(2))
      store.currentIndex = 1
      store.repeatMode = 'all'
      store.onTrackEnded()
      expect(store.currentIndex).toBe(0)
    })

    it('does not advance at end with repeat off', () => {
      store.addToEnd(makeItem(1))
      store.currentIndex = 0
      store.repeatMode = 'off'
      store.onTrackEnded()
      // stays at 0, no advancement since there's only one item
      expect(store.currentIndex).toBe(0)
    })
  })
})
