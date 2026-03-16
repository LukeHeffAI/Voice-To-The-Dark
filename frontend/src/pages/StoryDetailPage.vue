<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { Story } from '../api/types'
import * as storiesApi from '../api/stories'
import * as audioApi from '../api/audio'
import { useNotificationStore } from '../stores/notifications'
import { usePlayerStore } from '../stores/player'
import SeriesParts from '../components/SeriesParts.vue'
import TaskProgress from '../components/TaskProgress.vue'

const route = useRoute()
const router = useRouter()
const notifications = useNotificationStore()
const player = usePlayerStore()

const storyId = computed(() => Number(route.params.id))
const story = ref<Story | null>(null)
const loading = ref(true)
const hasScript = ref(false)
const resumePosition = ref(0)

// Task tracking
const activeTaskId = ref<number | null>(null)
const activeTaskType = ref<'script' | 'narration' | null>(null)

async function loadStory() {
  loading.value = true
  try {
    story.value = await storiesApi.getStory(storyId.value)
    // Check for script
    try {
      await audioApi.getScript(storyId.value)
      hasScript.value = true
    } catch {
      hasScript.value = false
    }
    // Check resume position
    try {
      const pb = await storiesApi.getPlayback(storyId.value)
      resumePosition.value = pb.position_seconds
    } catch {
      resumePosition.value = 0
    }
    // Check for active task (page reload recovery)
    try {
      const active = await audioApi.getActiveTask(storyId.value)
      activeTaskId.value = active.id
      activeTaskType.value = active.task_type
    } catch {
      // No active task — normal state
    }
  } catch {
    notifications.show('Story not found', 'error')
    router.push({ name: 'home' })
  } finally {
    loading.value = false
  }
}

async function generateScript() {
  try {
    const { task_id } = await audioApi.generateScript(storyId.value)
    activeTaskId.value = task_id
    activeTaskType.value = 'script'
  } catch (e) {
    notifications.show(e instanceof Error ? e.message : 'Failed to start script generation', 'error')
  }
}

async function generateAudio(forceRegenerate = false) {
  if (forceRegenerate && !confirm('Regenerate audio? This will replace the existing file.')) return
  try {
    const { task_id } = await audioApi.generateNarration(storyId.value, {
      force_regenerate: forceRegenerate,
    })
    activeTaskId.value = task_id
    activeTaskType.value = 'narration'
  } catch (e) {
    notifications.show(
      e instanceof Error ? e.message : 'Failed to start audio generation',
      'error',
    )
  }
}

function onTaskCompleted() {
  if (activeTaskType.value === 'script') {
    hasScript.value = true
    notifications.show('Script generated', 'success')
  } else if (activeTaskType.value === 'narration') {
    // Reload story to get updated audio_file_path
    storiesApi.getStory(storyId.value).then((s) => {
      story.value = s
    })
    notifications.show('Audio generated', 'success')
  }
  activeTaskId.value = null
  activeTaskType.value = null
}

function onTaskFailed(error: string) {
  notifications.show(error || 'Generation failed', 'error')
  activeTaskId.value = null
  activeTaskType.value = null
}

function playStory() {
  if (!story.value) return
  player.loadTrack(story.value.id, story.value.title, story.value.author || '', true)
  router.push({ name: 'player', params: { id: story.value.id } })
}

const wordCount = computed(() => {
  if (!story.value?.narration_text) return 0
  return story.value.narration_text.split(/\s+/).filter(Boolean).length
})

const pipelineStep = computed(() => {
  if (story.value?.audio_file_path) return 3
  if (hasScript.value) return 2
  return 1
})

const isGenerating = computed(() => activeTaskId.value !== null)

onMounted(loadStory)
</script>

<template>
  <div v-if="loading" class="loading">Loading story...</div>
  <div v-else-if="story">
    <RouterLink to="/" class="back-link">&larr; Back to stories</RouterLink>

    <h1 class="detail-title">{{ story.title }}</h1>
    <div class="detail-meta">
      <span v-if="story.author">by {{ story.author }}</span>
      <span v-if="story.part_count > 1" class="parts-badge">{{ story.part_count }} parts</span>
      <span class="word-count">{{ wordCount.toLocaleString() }} words</span>
    </div>

    <!-- Pipeline -->
    <div class="pipeline">
      <div class="step" :class="{ done: true }">
        <div class="step-num"><span class="check">&#10003;</span></div>
        <span>Story Fetched</span>
      </div>
      <div class="step" :class="{ done: hasScript, active: pipelineStep === 1 }">
        <div class="step-num">
          <span v-if="hasScript" class="check">&#10003;</span><span v-else>2</span>
        </div>
        <span>Script Generated</span>
      </div>
      <div class="step" :class="{ done: !!story.audio_file_path, active: pipelineStep === 2 }">
        <div class="step-num">
          <span v-if="story.audio_file_path" class="check">&#10003;</span><span v-else>3</span>
        </div>
        <span>Audio Ready</span>
      </div>
    </div>

    <!-- Task progress -->
    <TaskProgress
      v-if="activeTaskId"
      :task-id="activeTaskId"
      @completed="onTaskCompleted"
      @failed="onTaskFailed"
    />

    <!-- Actions -->
    <div class="actions">
      <!-- Step 2: Generate script -->
      <button
        v-if="!hasScript && !isGenerating"
        class="action-btn primary"
        @click="generateScript"
      >
        Generate Script
      </button>

      <!-- Step 3: Generate audio -->
      <button
        v-else-if="hasScript && !story.audio_file_path && !isGenerating"
        class="action-btn primary"
        @click="generateAudio()"
      >
        Generate Audio
      </button>

      <!-- All done: play/read/edit -->
      <template v-else-if="story.audio_file_path && !isGenerating">
        <button class="action-btn primary" @click="playStory">
          &#9654; {{ resumePosition > 0 ? 'Resume' : 'Listen' }}
        </button>
        <button class="action-btn" @click="generateAudio(true)">
          Regenerate Audio
        </button>
      </template>

      <!-- Always available if script exists -->
      <RouterLink
        v-if="hasScript && !isGenerating"
        :to="{ name: 'script-editor', params: { id: storyId } }"
        class="action-btn"
      >
        Edit Script
      </RouterLink>
      <RouterLink
        v-if="!isGenerating"
        :to="{ name: 'reader', params: { id: storyId } }"
        class="action-btn"
      >
        Read Story
      </RouterLink>
    </div>

    <!-- Series parts -->
    <SeriesParts :story-id="storyId" />
  </div>
</template>

<style scoped>
.loading {
  text-align: center;
  padding: 3rem;
  color: #555;
}

.back-link {
  display: inline-block;
  color: #555;
  text-decoration: none;
  font-size: 0.8rem;
  margin-bottom: 1rem;
  transition: color 0.15s;
}
.back-link:hover {
  color: #8a8a8a;
}

.detail-title {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 1.8rem;
  font-weight: 400;
  color: rgba(255, 255, 255, 0.9);
  line-height: 1.2;
  margin-bottom: 0.5rem;
}

.detail-meta {
  display: flex;
  gap: 0.75rem;
  font-size: 0.78rem;
  color: #8a8a8a;
  margin-bottom: 1.5rem;
}
.parts-badge {
  color: var(--color-info);
  font-weight: 500;
}
.word-count {
  color: #555;
}

/* Pipeline */
.pipeline {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
}
.step {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.6rem 0.7rem;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 8px;
  font-size: 0.75rem;
  color: #555;
}
.step.done {
  border-color: rgba(58, 125, 92, 0.25);
  background: rgba(58, 125, 92, 0.05);
  color: var(--color-success);
}
.step.active {
  border-color: rgba(160, 32, 32, 0.25);
  background: rgba(160, 32, 32, 0.05);
  color: var(--color-accent);
}
.step-num {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.65rem;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.04);
  flex-shrink: 0;
}
.check {
  font-size: 0.6rem;
}

/* Actions */
.actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
}
.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.55rem 1rem;
  border-radius: 8px;
  font-size: 0.8rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  text-decoration: none;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: #e8e6e3;
}
.action-btn:hover {
  background: rgba(255, 255, 255, 0.06);
}
.action-btn.primary {
  background: var(--color-accent);
  border-color: transparent;
  color: white;
}
.action-btn.primary:hover {
  background: var(--color-accent-hover);
}
</style>
