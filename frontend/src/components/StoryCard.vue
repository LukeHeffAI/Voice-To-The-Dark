<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import type { Folder, StoryListItem } from '../api/types'
import StoryCardMenu from './StoryCardMenu.vue'

const props = defineProps<{
  story: StoryListItem
  folders: Folder[]
  folderContext?: { folderId: number }
}>()

const emit = defineEmits<{ removed: [] }>()
const router = useRouter()
const menuOpen = ref(false)

function statusBadge() {
  if (props.story.has_audio) return { label: 'Ready to listen', cls: 'badge-success' }
  if (props.story.has_script) return { label: 'Script ready', cls: 'badge-info' }
  return { label: 'Fetched', cls: 'badge-neutral' }
}

function goToStory() {
  router.push({ name: 'story-detail', params: { id: props.story.id } })
}
</script>

<template>
  <div class="story-card" @click="goToStory">
    <div class="card-top">
      <h3 class="card-title">{{ story.title }}</h3>
      <div class="card-actions" @click.stop>
        <button class="menu-trigger" @click="menuOpen = !menuOpen">⋯</button>
        <StoryCardMenu
          v-if="menuOpen"
          :story="story"
          :folders="folders"
          :folder-context="folderContext"
          @close="menuOpen = false"
          @removed="emit('removed')"
        />
      </div>
    </div>

    <div class="card-meta">
      <span v-if="story.author" class="card-author">{{ story.author }}</span>
      <span v-if="story.part_count > 1" class="card-parts">{{ story.part_count }} parts</span>
    </div>

    <div class="card-bottom">
      <span class="badge" :class="statusBadge().cls">{{ statusBadge().label }}</span>
    </div>
  </div>
</template>

<style scoped>
.story-card {
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 10px;
  padding: 0.9rem 1rem;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  position: relative;
}
.story-card:hover {
  background: rgba(255, 255, 255, 0.04);
  transform: translateY(-1px);
}

.card-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.5rem;
}

.card-title {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 1.05rem;
  font-weight: 500;
  color: #e8e6e3;
  line-height: 1.3;
  flex: 1;
  min-width: 0;
}

.card-actions {
  position: relative;
  flex-shrink: 0;
}

.menu-trigger {
  background: none;
  border: none;
  color: #555;
  font-size: 1.1rem;
  cursor: pointer;
  padding: 0.2rem 0.4rem;
  border-radius: 6px;
  transition: all 0.15s;
  line-height: 1;
}
.menu-trigger:hover {
  color: #8a8a8a;
  background: rgba(255, 255, 255, 0.04);
}

.card-meta {
  display: flex;
  gap: 0.75rem;
  margin-top: 0.4rem;
  font-size: 0.75rem;
  color: #555;
}
.card-author {
  color: #8a8a8a;
}
.card-parts {
  color: var(--color-info);
  font-weight: 500;
}

.card-bottom {
  margin-top: 0.6rem;
}

.badge {
  display: inline-block;
  padding: 0.15rem 0.55rem;
  border-radius: 20px;
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.badge-success {
  background: rgba(58, 125, 92, 0.12);
  color: var(--color-success);
}
.badge-info {
  background: rgba(104, 104, 184, 0.12);
  color: var(--color-info);
}
.badge-neutral {
  background: rgba(255, 255, 255, 0.04);
  color: #555;
}
</style>
