import { defineStore } from 'pinia'
import { ref } from 'vue'
import { usePlayerStore } from './player'
import type { PlaylistItem, RepeatMode } from '@/types'

export const usePlaylistStore = defineStore(
  'playlist',
  () => {
    const items = ref<PlaylistItem[]>([])
    const currentIndex = ref(0)
    const repeatMode = ref<RepeatMode>('off')

    function getPlayer() {
      return usePlayerStore()
    }

    // ── Queue operations ─────────────────────────────
    function addNext(item: PlaylistItem) {
      const insertIdx = currentIndex.value + 1
      items.value.splice(insertIdx, 0, { ...item })
    }

    function addToEnd(item: PlaylistItem) {
      items.value.push({ ...item })
    }

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

    function reorder(oldIndex: number, newIndex: number) {
      if (oldIndex === newIndex) return
      if (oldIndex < 0 || oldIndex >= items.value.length) return
      if (newIndex < 0 || newIndex >= items.value.length) return

      const item = items.value.splice(oldIndex, 1)[0]
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

    function playAt(index: number) {
      if (index < 0 || index >= items.value.length) return
      currentIndex.value = index
      const track = items.value[index]
      getPlayer().loadTrack(track.storyId)
    }

    function next() {
      if (items.value.length === 0) return
      if (currentIndex.value < items.value.length - 1) {
        playAt(currentIndex.value + 1)
      } else if (repeatMode.value === 'all') {
        playAt(0)
      }
    }

    function prev() {
      if (items.value.length === 0) return
      const player = getPlayer()

      // If more than 3 seconds in, restart current track
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

    function clear() {
      items.value = []
      currentIndex.value = 0
    }

    function toggleRepeat() {
      const modes: RepeatMode[] = ['off', 'all', 'one']
      const idx = modes.indexOf(repeatMode.value)
      repeatMode.value = modes[(idx + 1) % 3]
    }

    /** Ensure the given track is in the playlist and set as current */
    function ensureCurrent(item: PlaylistItem) {
      if (
        items.value.length === 0 ||
        !items.value[currentIndex.value] ||
        items.value[currentIndex.value].storyId !== item.storyId
      ) {
        const found = items.value.findIndex((i) => i.storyId === item.storyId)
        if (found >= 0) {
          currentIndex.value = found
        } else {
          items.value.unshift({ ...item })
          currentIndex.value = 0
        }
      }
    }

    /** Handle track end — called by App shell */
    function onTrackEnded() {
      if (repeatMode.value === 'one') {
        const player = getPlayer()
        player.seek(0)
        player.play()
        return
      }

      if (currentIndex.value < items.value.length - 1) {
        playAt(currentIndex.value + 1)
      } else if (repeatMode.value === 'all' && items.value.length > 0) {
        playAt(0)
      }
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
      onTrackEnded,
    }
  },
  {
    persist: true,
  },
)
