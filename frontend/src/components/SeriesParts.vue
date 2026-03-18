<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { SeriesPart } from '../api/types'
import * as storiesApi from '../api/stories'
import { useNotificationStore } from '../stores/notifications'

const props = defineProps<{ storyId: number }>()

const router = useRouter()
const notifications = useNotificationStore()

const parts = ref<SeriesPart[]>([])
const loading = ref(true)
const seriesWordCount = ref(0)
const seriesEstMinutes = ref(0)

async function loadParts() {
  loading.value = true
  try {
    const data = await storiesApi.getSeriesParts(props.storyId)
    parts.value = data.parts
    seriesWordCount.value = data.series_word_count
    seriesEstMinutes.value = data.series_est_minutes
  } catch {
    // Not a series story — no parts
    parts.value = []
  } finally {
    loading.value = false
  }
}

function goToPart(part: SeriesPart) {
  if (part.story_id) {
    router.push({ name: 'story-detail', params: { id: part.story_id } })
  } else {
    submitPart(part)
  }
}

async function submitPart(part: SeriesPart) {
  try {
    const story = await storiesApi.submitStory(part.url)
    notifications.show(`Submitted: ${story.title}`, 'success')
    part.story_id = story.id
  } catch {
    notifications.show('Failed to submit part', 'error')
  }
}

onMounted(loadParts)
</script>

<template>
  <div v-if="loading" class="series-loading">Loading series...</div>
  <div v-else-if="parts.length > 1" class="series-section">
    <h3 class="series-heading">
      Series ({{ parts.length }} parts)
      <span v-if="seriesEstMinutes > 0" class="series-meta">
        ~{{ seriesEstMinutes }} min read
      </span>
    </h3>
    <ul class="series-list">
      <li
        v-for="(part, i) in parts"
        :key="part.url"
        class="series-item"
        :class="{ 'is-current': part.story_id === storyId }"
        @click="goToPart(part)"
      >
        <span class="part-number">{{ i + 1 }}</span>
        <div class="part-info">
          <span class="part-title">{{ part.title }}</span>
          <span v-if="!part.story_id" class="part-unsubmitted">Click to submit</span>
        </div>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.series-loading {
  color: #555;
  font-size: 0.8rem;
  padding: 0.5rem 0;
}

.series-section {
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.series-heading {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 1rem;
  font-weight: 500;
  color: var(--color-info);
  margin-bottom: 0.75rem;
}
.series-meta {
  font-family: Inter, system-ui, sans-serif;
  font-size: 0.72rem;
  color: #555;
  font-weight: 400;
  margin-left: 0.5rem;
}

.series-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.series-item {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.5rem 0.65rem;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
}
.series-item:hover {
  background: rgba(255, 255, 255, 0.03);
}
.series-item.is-current {
  background: rgba(104, 104, 184, 0.08);
}

.part-number {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.65rem;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.04);
  color: #8a8a8a;
  flex-shrink: 0;
}

.part-info {
  flex: 1;
  min-width: 0;
}
.part-title {
  display: block;
  font-size: 0.8rem;
  color: #e8e6e3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.part-unsubmitted {
  font-size: 0.7rem;
  color: var(--color-accent);
}
</style>
