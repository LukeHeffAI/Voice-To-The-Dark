import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { TrackInfo } from '../api/types'
import { usePlayerStore } from './player'

export type RepeatMode = 'off' | 'all' | 'one'

export const usePlaylistStore = defineStore(
  'playlist',
  () => {
    const items = ref<TrackInfo[]>([])
    const currentIndex = ref(0)
    const repeatMode = ref<RepeatMode>('off')

    let _initialized = false

    /** Add a track right after the current one. */
    function addNext(info: TrackInfo) {
      items.value.splice(currentIndex.value + 1, 0, { ...info })
    }

    /** Add a track to the end of the queue. */
    function addToEnd(info: TrackInfo) {
      items.value.push({ ...info })
    }

    /** Remove the track at the given index. */
    function removeAt(index: number) {
      if (index < 0 || index >= items.value.length) return
      items.value.splice(index, 1)
      if (items.value.length === 0) {
        currentIndex.value = 0
      } else if (index < currentIndex.value) {
        currentIndex.value--
      } else if (index === currentIndex.value && currentIndex.value >= items.value.length) {
        currentIndex.value = items.value.length - 1
      }
    }

    /** Reorder: move item from oldIndex to newIndex (for drag-and-drop). */
    function reorder(oldIndex: number, newIndex: number) {
      if (oldIndex === newIndex) return
      if (oldIndex < 0 || oldIndex >= items.value.length) return
      if (newIndex < 0 || newIndex >= items.value.length) return

      const item = items.value.splice(oldIndex, 1)[0]!
      items.value.splice(newIndex, 0, item)

      // Adjust currentIndex to follow the currently-playing track
      if (currentIndex.value === oldIndex) {
        currentIndex.value = newIndex
      } else if (oldIndex < currentIndex.value && newIndex >= currentIndex.value) {
        currentIndex.value--
      } else if (oldIndex > currentIndex.value && newIndex <= currentIndex.value) {
        currentIndex.value++
      }
    }

    /** Play a specific item by index. */
    function playAt(index: number) {
      if (index < 0 || index >= items.value.length) return
      currentIndex.value = index
      const track = items.value[index]!
      const player = usePlayerStore()
      player.loadTrack(track.storyId, track.title, track.author, true)
    }

    /** Advance to next track, respecting repeat mode. */
    function next() {
      if (items.value.length === 0) return
      if (currentIndex.value < items.value.length - 1) {
        playAt(currentIndex.value + 1)
      } else if (repeatMode.value === 'all') {
        playAt(0)
      }
    }

    /** Go to previous track, or restart current if >3s in. */
    function prev() {
      if (items.value.length === 0) return
      const player = usePlayerStore()

      if (player.currentTime > 3) {
        player.seek(0)
        player.play()
        return
      }

      if (currentIndex.value > 0) {
        playAt(currentIndex.value - 1)
      } else if (repeatMode.value === 'all') {
        playAt(items.value.length - 1)
      } else {
        player.seek(0)
        player.play()
      }
    }

    /** Clear the entire queue. */
    function clear() {
      items.value = []
      currentIndex.value = 0
    }

    /** Cycle repeat mode: off → all → one → off. */
    function toggleRepeat() {
      const modes: RepeatMode[] = ['off', 'all', 'one']
      const idx = modes.indexOf(repeatMode.value)
      repeatMode.value = modes[(idx + 1) % 3] ?? 'off'
    }

    /** Ensure the currently-playing track is in the playlist. */
    function ensureCurrent(info: TrackInfo) {
      if (
        items.value.length === 0 ||
        !items.value[currentIndex.value] ||
        items.value[currentIndex.value]!.storyId !== info.storyId
      ) {
        const found = items.value.findIndex((i) => i.storyId === info.storyId)
        if (found >= 0) {
          currentIndex.value = found
        } else {
          items.value.unshift({ ...info })
          currentIndex.value = 0
        }
      }
    }

    function getCurrentTrack(): TrackInfo | null {
      return items.value[currentIndex.value] ?? null
    }

    /** Initialize auto-advance on track end. Call once from App.vue. */
    function initAutoAdvance() {
      if (_initialized) return
      _initialized = true

      const player = usePlayerStore()
      player.onEnded(() => {
        if (repeatMode.value === 'one') {
          player.seek(0)
          player.play()
          return
        }
        if (currentIndex.value < items.value.length - 1) {
          playAt(currentIndex.value + 1)
        } else if (repeatMode.value === 'all' && items.value.length > 0) {
          playAt(0)
        }
      })
    }

    return {
      items,
      currentIndex,
      repeatMode,
      addNext,
      addToEnd,
      removeAt,
      reorder,
      playAt,
      next,
      prev,
      clear,
      toggleRepeat,
      ensureCurrent,
      getCurrentTrack,
      initAutoAdvance,
    }
  },
  {
    persist: true,
  },
)
