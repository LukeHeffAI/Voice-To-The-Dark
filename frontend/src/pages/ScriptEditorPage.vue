<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import type { NarrationScript, ScriptSegment, SegmentType } from '../api/types'
import * as audioApi from '../api/audio'
import { useNotificationStore } from '../stores/notifications'

const route = useRoute()
const notifications = useNotificationStore()

const storyId = computed(() => Number(route.params.id))
const script = ref<NarrationScript | null>(null)
const storyTitle = ref('')
const loading = ref(true)
const saving = ref(false)
const saveStatus = ref('')
const saveStatusType = ref<'success' | 'error' | ''>('')
const hasChanges = ref(false)
const editingIndex = ref<number | null>(null)

// Editing state for the currently active segment
const editText = ref('')
const editTone = ref('')
const editCharacter = ref('')
const editDescription = ref('')
const editDurationMs = ref(1500)

async function loadScript() {
  loading.value = true
  try {
    const data = await audioApi.getScript(storyId.value)
    script.value = data.script
    storyTitle.value = data.script.title
  } catch {
    notifications.show('Script not found', 'error')
  } finally {
    loading.value = false
  }
}

function isVoiceSegment(seg: ScriptSegment) {
  return seg.type === 'narration' || seg.type === 'dialogue'
}

function isPauseSegment(seg: ScriptSegment) {
  return seg.type === 'pause'
}

function typeClass(type: SegmentType) {
  return `type-${type}`
}

// Character editing
function onProfileChange(charKey: string, value: string) {
  if (!script.value || !script.value.characters[charKey]) return
  script.value.characters[charKey]!.voice_profile = value
  hasChanges.value = true
}

function onVoiceIdChange(charKey: string, value: string) {
  if (!script.value || !script.value.characters[charKey]) return
  script.value.characters[charKey]!.voice_id = value || null
  hasChanges.value = true
}

// Segment editing
function startEdit(index: number) {
  if (!script.value) return
  if (editingIndex.value === index) {
    cancelEdit()
    return
  }

  editingIndex.value = index
  const seg = script.value.segments[index]!
  editText.value = seg.text || ''
  editTone.value = seg.tone || ''
  editCharacter.value = seg.character || ''
  editDescription.value = seg.description || ''
  editDurationMs.value = seg.duration_ms || 1500
}

function confirmEdit() {
  if (!script.value || editingIndex.value === null) return
  const seg = script.value.segments[editingIndex.value]
  if (!seg) return

  if (isVoiceSegment(seg)) {
    seg.text = editText.value
    seg.tone = editTone.value
    seg.character = editCharacter.value
  } else if (isPauseSegment(seg)) {
    seg.duration_ms = editDurationMs.value || 1500
  } else {
    seg.description = editDescription.value
  }

  hasChanges.value = true
  editingIndex.value = null
}

function cancelEdit() {
  editingIndex.value = null
}

function deleteSegment(index: number) {
  if (!script.value) return
  if (!confirm('Delete this segment?')) return
  script.value.segments.splice(index, 1)
  hasChanges.value = true
  editingIndex.value = null
}

async function saveScript() {
  if (!script.value) return
  saving.value = true
  saveStatus.value = ''

  try {
    await audioApi.updateScript(storyId.value, script.value)
    saveStatus.value = 'Saved'
    saveStatusType.value = 'success'
    hasChanges.value = false
    notifications.show('Script saved', 'success')
  } catch (e) {
    saveStatus.value = e instanceof Error ? e.message : 'Save failed'
    saveStatusType.value = 'error'
    notifications.show('Save failed', 'error')
  } finally {
    saving.value = false
  }
}

// Warn before leaving with unsaved changes
function onBeforeUnload(e: BeforeUnloadEvent) {
  if (hasChanges.value) {
    e.preventDefault()
    e.returnValue = ''
  }
}

onMounted(() => {
  window.addEventListener('beforeunload', onBeforeUnload)
  loadScript()
})

onUnmounted(() => {
  window.removeEventListener('beforeunload', onBeforeUnload)
})

const characterEntries = computed(() => {
  if (!script.value) return []
  return Object.entries(script.value.characters)
})

const segmentCount = computed(() => script.value?.segments.length ?? 0)
</script>

<template>
  <div v-if="loading" class="loading">Loading script...</div>
  <div v-else-if="script" class="page-container">
    <RouterLink :to="{ name: 'story-detail', params: { id: storyId } }" class="back-link">
      &larr; Back to story
    </RouterLink>

    <div class="page-header">
      <div>
        <h1 class="header-title">Edit Script</h1>
        <div class="subtitle">{{ storyTitle }}</div>
      </div>
      <div class="save-area">
        <button class="save-btn" :disabled="saving" @click="saveScript">
          {{ saving ? 'Saving...' : 'Save Changes' }}
        </button>
        <div v-if="saveStatus" class="save-status" :class="saveStatusType">
          {{ saveStatus }}
        </div>
      </div>
    </div>

    <div class="regen-notice">
      Saving changes to the script will require audio regeneration.
    </div>

    <!-- Characters panel -->
    <div class="characters-panel">
      <h2 class="panel-heading">Characters &amp; Voices</h2>
      <div class="character-list">
        <div
          v-for="[key, profile] in characterEntries"
          :key="key"
          class="character-card"
        >
          <div class="char-card-header">
            <span class="char-card-name" :class="key === 'narrator' ? 'narrator' : 'dialogue'">
              {{ key }}
            </span>
            <span class="char-card-badge" :class="key === 'narrator' ? 'narrator' : 'dialogue'">
              {{ key === 'narrator' ? 'narrator' : 'dialogue' }}
            </span>
          </div>

          <div class="char-field">
            <div class="char-field-label">Voice profile</div>
            <input
              class="char-field-input"
              :value="profile.voice_profile"
              placeholder="e.g. deep, steady, ominous"
              @change="(e: Event) => onProfileChange(key, (e.target as HTMLInputElement).value)"
            />
          </div>

          <div class="char-field">
            <div class="char-field-label">Voice ID (optional)</div>
            <input
              class="char-field-input"
              :value="profile.voice_id || ''"
              placeholder="Auto (best match)"
              @change="(e: Event) => onVoiceIdChange(key, (e.target as HTMLInputElement).value)"
            />
            <div v-if="!profile.voice_id" class="char-voice-hint">
              Matched automatically from voice profile when generating audio
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Segments -->
    <div class="segments-header">
      <h2 class="segments-title">Segments</h2>
      <div class="segment-count">{{ segmentCount }} segments</div>
    </div>
    <p class="click-hint">Tap a segment to edit it</p>

    <div class="segment-list">
      <div
        v-for="(seg, i) in script.segments"
        :key="i"
        class="segment-card"
        :class="{ editing: editingIndex === i }"
        @click="startEdit(i)"
      >
        <div class="segment-top">
          <span class="segment-type" :class="typeClass(seg.type)">{{ seg.type }}</span>
          <span v-if="seg.character" class="segment-character">{{ seg.character }}</span>
          <span v-if="seg.tone" class="segment-tone">{{ seg.tone }}</span>
          <span class="segment-index">#{{ i + 1 }}</span>
        </div>

        <!-- Display mode -->
        <div v-if="editingIndex !== i" class="segment-display">
          <div v-if="isVoiceSegment(seg)" class="segment-text">{{ seg.text }}</div>
          <div v-else-if="isPauseSegment(seg)" class="segment-description">
            {{ seg.duration_ms || 1500 }}ms pause
          </div>
          <div v-else class="segment-description">{{ seg.description }}</div>
        </div>

        <!-- Edit mode -->
        <div v-if="editingIndex === i" class="segment-edit" @click.stop>
          <template v-if="isVoiceSegment(seg)">
            <textarea v-model="editText" class="edit-field" />
            <div class="edit-row">
              <input v-model="editTone" class="edit-field" placeholder="Tone (e.g. foreboding)" />
              <input v-model="editCharacter" class="edit-field" placeholder="Character" />
            </div>
          </template>
          <template v-else-if="isPauseSegment(seg)">
            <input v-model.number="editDurationMs" type="number" class="edit-field" placeholder="Duration (ms)" />
          </template>
          <template v-else>
            <textarea v-model="editDescription" class="edit-field" />
          </template>

          <div class="edit-actions">
            <button class="edit-btn edit-btn-save" @click.stop="confirmEdit()">Done</button>
            <button class="edit-btn edit-btn-cancel" @click.stop="cancelEdit()">Cancel</button>
            <button class="edit-btn edit-btn-delete" @click.stop="deleteSegment(i)">Delete</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.loading {
  text-align: center;
  padding: 3rem;
  color: #555;
}

.page-container {
  max-width: 720px;
  margin: 0 auto;
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

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 1.25rem 0 1.75rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  margin-bottom: 1.25rem;
  gap: 1rem;
  flex-wrap: wrap;
}
.header-title {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 1.5rem;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.9);
}
.subtitle {
  font-size: 0.8rem;
  color: #555;
  margin-top: 0.25rem;
  letter-spacing: 0.02em;
}

.save-area {
  text-align: right;
}
.save-btn {
  padding: 0.6rem 1.5rem;
  border: none;
  border-radius: 6px;
  background: var(--color-accent);
  color: #fff;
  font-family: inherit;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.25s;
  white-space: nowrap;
  letter-spacing: 0.02em;
}
.save-btn:hover {
  background: var(--color-accent-hover);
}
.save-btn:disabled {
  background: rgba(255, 255, 255, 0.06);
  color: #555;
  cursor: not-allowed;
}

.save-status {
  font-size: 0.78rem;
  color: #555;
  text-align: right;
  margin-top: 0.3rem;
}
.save-status.error {
  color: #e07070;
}
.save-status.success {
  color: var(--color-success);
}

.regen-notice {
  margin-bottom: 1.5rem;
  padding: 0.75rem 1rem;
  background: rgba(255, 170, 0, 0.1);
  border-left: 3px solid #fa0;
  border-radius: 4px;
  font-size: 0.9rem;
  color: #b0b0b0;
}

/* Characters panel */
.characters-panel {
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 10px;
  padding: 1.1rem 1.3rem;
  margin-bottom: 1.25rem;
}
.panel-heading {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 1rem;
  font-weight: 500;
  color: #8a8a8a;
  margin-bottom: 0.85rem;
  letter-spacing: 0.03em;
}
.character-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.character-card {
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 6px;
  padding: 0.85rem 1rem;
}
.char-card-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.65rem;
}
.char-card-name {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 0.95rem;
  font-weight: 600;
}
.char-card-name.narrator {
  color: var(--color-success);
}
.char-card-name.dialogue {
  color: var(--color-info);
}
.char-card-badge {
  font-size: 0.6rem;
  font-weight: 600;
  text-transform: uppercase;
  padding: 0.12rem 0.4rem;
  border-radius: 4px;
  letter-spacing: 0.05em;
}
.char-card-badge.narrator {
  background: rgba(58, 125, 92, 0.12);
  color: var(--color-success);
}
.char-card-badge.dialogue {
  background: rgba(104, 104, 184, 0.12);
  color: var(--color-info);
}
.char-field {
  margin-bottom: 0.5rem;
}
.char-field:last-child {
  margin-bottom: 0;
}
.char-field-label {
  font-size: 0.65rem;
  color: #555;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 0.25rem;
}
.char-field-input {
  width: 100%;
  padding: 0.45rem 0.65rem;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.025);
  color: #e8e6e3;
  font-family: inherit;
  font-size: 0.8rem;
  outline: none;
  transition: border-color 0.2s;
}
.char-field-input:focus {
  border-color: rgba(160, 32, 32, 0.4);
}
.char-voice-hint {
  font-size: 0.68rem;
  color: #555;
  margin-top: 0.2rem;
  font-style: italic;
}

/* Segments */
.segments-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.85rem;
}
.segments-title {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 1.05rem;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.9);
  letter-spacing: 0.03em;
}
.segment-count {
  font-size: 0.78rem;
  color: #555;
}

.click-hint {
  font-size: 0.72rem;
  color: #555;
  text-align: center;
  margin-bottom: 1rem;
  letter-spacing: 0.03em;
}

.segment-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.segment-card {
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 6px;
  padding: 0.85rem 1rem;
  transition: all 0.2s;
  cursor: pointer;
}
.segment-card:hover {
  border-color: rgba(255, 255, 255, 0.12);
}
.segment-card.editing {
  border-color: rgba(160, 32, 32, 0.4);
  background: rgba(255, 255, 255, 0.04);
  cursor: default;
}

.segment-top {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.4rem;
}
.segment-type {
  font-size: 0.62rem;
  font-weight: 700;
  text-transform: uppercase;
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
  letter-spacing: 0.05em;
}
.type-narration {
  background: rgba(58, 125, 92, 0.12);
  color: var(--color-success);
}
.type-dialogue {
  background: rgba(104, 104, 184, 0.12);
  color: var(--color-info);
}
.type-sfx {
  background: rgba(255, 170, 0, 0.12);
  color: #fa0;
}
.type-ambient {
  background: rgba(0, 180, 180, 0.12);
  color: #0bb;
}
.type-pause {
  background: rgba(255, 255, 255, 0.025);
  color: #555;
}

.segment-character {
  font-size: 0.78rem;
  color: #8a8a8a;
  font-weight: 500;
}
.segment-tone {
  font-size: 0.72rem;
  color: #555;
  font-style: italic;
  margin-left: auto;
}
.segment-index {
  font-size: 0.68rem;
  color: #555;
  margin-left: auto;
  font-variant-numeric: tabular-nums;
}

.segment-text {
  font-size: 0.82rem;
  color: #8a8a8a;
  line-height: 1.5;
  word-break: break-word;
}
.segment-description {
  font-size: 0.82rem;
  color: #555;
  font-style: italic;
}

/* Edit mode */
.segment-edit {
  margin-top: 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.edit-field {
  width: 100%;
  padding: 0.5rem 0.7rem;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.2);
  color: #e8e6e3;
  font-family: inherit;
  font-size: 0.82rem;
  resize: vertical;
  outline: none;
  transition: border-color 0.2s;
}
.edit-field:focus {
  border-color: rgba(160, 32, 32, 0.4);
}

textarea.edit-field {
  min-height: 60px;
}

.edit-row {
  display: flex;
  gap: 0.5rem;
}
.edit-row .edit-field {
  flex: 1;
}

.edit-actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.3rem;
}
.edit-btn {
  padding: 0.35rem 0.85rem;
  border-radius: 6px;
  font-family: inherit;
  font-size: 0.78rem;
  cursor: pointer;
  border: none;
  transition: all 0.2s;
  font-weight: 500;
}
.edit-btn-save {
  background: rgba(58, 125, 92, 0.15);
  color: var(--color-success);
}
.edit-btn-save:hover {
  background: rgba(58, 125, 92, 0.2);
}
.edit-btn-cancel {
  background: rgba(255, 255, 255, 0.025);
  color: #8a8a8a;
}
.edit-btn-cancel:hover {
  background: rgba(255, 255, 255, 0.04);
}
.edit-btn-delete {
  background: rgba(204, 68, 68, 0.1);
  color: #e07070;
}
.edit-btn-delete:hover {
  background: rgba(204, 68, 68, 0.18);
}
</style>
