<script setup lang="ts">
import { ref } from 'vue'
import type { StoryListItem, Folder } from '@/types'
import StoryCardMenu from './StoryCardMenu.vue'

const props = defineProps<{
  story: StoryListItem
  folders?: Folder[]
  showFolderActions?: boolean
  folderId?: number
}>()

defineEmits<{
  hide: [storyId: number]
  removeFromFolder: [folderId: number, storyId: number]
  addToFolder: [folderId: number, storyId: number]
  addToQueue: [story: StoryListItem]
  playNext: [story: StoryListItem]
  createFolderAndAdd: [folderName: string, storyId: number]
}>()

const menuOpen = ref(false)

function toggleMenu(e: Event) {
  e.preventDefault()
  e.stopPropagation()
  menuOpen.value = !menuOpen.value
}

function closeMenu() {
  menuOpen.value = false
}

// Close on outside click
function onDocClick(e: Event) {
  const target = e.target as HTMLElement
  if (!target.closest('.card-menu-btn') && !target.closest('.card-dropdown')) {
    menuOpen.value = false
  }
}

// Register/unregister outside click
import { onMounted, onUnmounted } from 'vue'
onMounted(() => document.addEventListener('click', onDocClick))
onUnmounted(() => document.removeEventListener('click', onDocClick))

const storyLink = props.story.has_audio
  ? `/story/${props.story.id}/play`
  : `/story/${props.story.id}`
</script>

<template>
  <div class="story-card-wrapper">
    <router-link :to="storyLink" class="story-card">
      <div class="story-card-title">{{ story.title }}</div>
      <div class="story-card-meta">
        <span>{{ story.part_count }} part{{ story.part_count !== 1 ? 's' : '' }}</span>
        <span v-if="story.has_audio" class="badge badge-success">Ready to listen</span>
        <span v-else-if="story.has_script" class="badge badge-info">Script ready</span>
        <span v-else class="badge badge-muted">Fetched</span>
      </div>
    </router-link>

    <button class="card-menu-btn" @click="toggleMenu" aria-label="Story options">&#8942;</button>

    <StoryCardMenu
      v-if="menuOpen"
      :story="story"
      :folders="folders"
      :show-folder-actions="showFolderActions"
      :folder-id="folderId"
      @close="closeMenu"
      @hide="$emit('hide', story.id)"
      @remove-from-folder="$emit('removeFromFolder', folderId!, story.id)"
      @add-to-folder="(fid) => $emit('addToFolder', fid, story.id)"
      @add-to-queue="$emit('addToQueue', story)"
      @play-next="$emit('playNext', story)"
      @create-folder-and-add="(name) => $emit('createFolderAndAdd', name, story.id)"
    />
  </div>
</template>

<style scoped>
.story-card-wrapper { position: relative; }
.story-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 1.1rem 2.8rem 1.1rem 1.3rem;
  text-decoration: none;
  color: inherit;
  display: block;
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  backdrop-filter: blur(12px);
}
.story-card:hover {
  border-color: var(--color-border-hover);
  background: var(--color-surface-hover);
  transform: translateY(-1px);
}
.story-card-title {
  font-family: var(--font-family-serif);
  font-size: 1.2rem;
  font-weight: 500;
  color: var(--color-text-1);
  line-height: 1.35;
}
.story-card-meta {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-top: 0.5rem;
  font-size: 0.75rem;
  color: var(--color-text-3);
  letter-spacing: 0.02em;
}
.badge-muted {
  background: var(--color-surface);
  color: var(--color-text-3);
  border: 1px solid var(--color-border);
}
.card-menu-btn {
  position: absolute; top: 50%; right: 0.6rem; transform: translateY(-50%);
  width: 28px; height: 28px; display: flex; align-items: center; justify-content: center;
  background: transparent; border: none; border-radius: var(--radius-sm);
  color: var(--color-text-3); cursor: pointer; transition: all 0.2s;
  z-index: 2; font-size: 1.1rem; line-height: 1;
}
.card-menu-btn:hover { color: var(--color-text-1); background: var(--color-surface-active); }
</style>
