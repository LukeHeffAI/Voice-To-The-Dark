<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { audioApi, settingsApi } from '@/api/client'
import { useNotificationStore } from '@/stores/notifications'
import type { NarrationScript, ScriptSegment, SegmentType, VoiceEntry } from '@/types'

const route = useRoute()
const notify = useNotificationStore()

const storyId = computed(() => Number(route.params.id))
const storyTitle = ref('')
const script = ref<NarrationScript | null>(null)
const voicePool = ref<VoiceEntry[]>([])
const hasChanges = ref(false)
const saving = ref(false)
const saveStatus = ref<{ text: string; type: '' | 'success' | 'error' }>({ text: '', type: '' })
const editingIndex = ref<number | null>(null)
const loading = ref(true)

// ── Edit state for inline editor ──────────────────────────
const editText = ref('')
const editTone = ref('')
const editCharacter = ref('')
const editDurationMs = ref(1500)
const editDescription = ref('')

onMounted(async () => {
  try {
    const [scriptData, voices] = await Promise.all([
      audioApi.getScript(storyId.value),
      settingsApi.voices().catch(() => [] as VoiceEntry[]),
    ])
    script.value = scriptData.script
    storyTitle.value = scriptData.script.title
    voicePool.value = voices
  } catch {
    notify.show('Failed to load script', 'error')
  } finally {
    loading.value = false
  }
})

// Warn on navigation with unsaved changes
function beforeUnload(e: BeforeUnloadEvent) {
  if (hasChanges.value) {
    e.preventDefault()
    e.returnValue = ''
  }
}
onMounted(() => window.addEventListener('beforeunload', beforeUnload))
onBeforeUnmount(() => window.removeEventListener('beforeunload', beforeUnload))

// ── Characters ────────────────────────────────────────────
const characterEntries = computed(() => {
  if (!script.value) return []
  return Object.entries(script.value.characters)
})

function isNarrator(key: string): boolean {
  return key === 'narrator'
}

function onProfileChange(key: string, value: string) {
  if (!script.value) return
  script.value.characters[key].voice_profile = value
  hasChanges.value = true
}

function onVoiceChange(key: string, value: string) {
  if (!script.value) return
  script.value.characters[key].voice_id = value || null
  hasChanges.value = true
}

const maleVoices = computed(() => voicePool.value.filter((v) => v.gender === 'male'))
const femaleVoices = computed(() => voicePool.value.filter((v) => v.gender === 'female'))

function voiceLabel(v: VoiceEntry): string {
  return `${v.name} — ${v.archetypes.join(', ')}`
}

// ── Segments ──────────────────────────────────────────────
function isVoiceSegment(seg: ScriptSegment): boolean {
  return seg.type === 'narration' || seg.type === 'dialogue'
}

function isPauseSegment(seg: ScriptSegment): boolean {
  return seg.type === 'pause'
}

function toggleEdit(index: number) {
  if (editingIndex.value === index) {
    editingIndex.value = null
    return
  }
  if (!script.value) return
  const seg = script.value.segments[index]
  editText.value = seg.text || ''
  editTone.value = seg.tone || ''
  editCharacter.value = seg.character || ''
  editDurationMs.value = seg.duration_ms || 1500
  editDescription.value = seg.description || ''
  editingIndex.value = index
}

function confirmEdit() {
  if (editingIndex.value === null || !script.value) return
  const seg = script.value.segments[editingIndex.value]

  if (isVoiceSegment(seg)) {
    seg.text = editText.value
    seg.tone = editTone.value
    seg.character = editCharacter.value
  } else if (isPauseSegment(seg)) {
    seg.duration_ms = parseInt(String(editDurationMs.value)) || 1500
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
  if (!confirm('Delete this segment?')) return
  if (!script.value) return
  script.value.segments.splice(index, 1)
  hasChanges.value = true
  if (editingIndex.value === index) editingIndex.value = null
  else if (editingIndex.value !== null && editingIndex.value > index) editingIndex.value--
}

// ── Save ──────────────────────────────────────────────────
async function saveScript() {
  if (!script.value) return
  saving.value = true
  saveStatus.value = { text: '', type: '' }

  try {
    await audioApi.updateScript(storyId.value, script.value)
    saveStatus.value = { text: 'Saved', type: 'success' }
    hasChanges.value = false
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'Save failed'
    saveStatus.value = { text: msg, type: 'error' }
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="page-container">
    <router-link :to="`/story/${storyId}`" class="back-link">&larr; Back to story</router-link>

    <div v-if="loading" class="text-center py-8">
      <span class="spinner spinner-lg"></span>
    </div>

    <template v-else-if="script">
      <div class="page-header">
        <div>
          <h1>Edit Script</h1>
          <div class="subtitle">{{ storyTitle }}</div>
        </div>
        <div>
          <button class="save-btn" :disabled="saving" @click="saveScript">
            {{ saving ? 'Saving...' : 'Save Changes' }}
          </button>
          <div
            v-if="saveStatus.text"
            class="save-status"
            :class="saveStatus.type"
          >{{ saveStatus.text }}</div>
        </div>
      </div>

      <div class="regen-notice">
        Saving changes to the script will require audio regeneration.
      </div>

      <!-- Characters panel -->
      <div class="characters-panel">
        <h2>Characters &amp; Voices</h2>
        <div class="character-list">
          <div v-for="[key, profile] in characterEntries" :key="key" class="character-card">
            <div class="char-card-header">
              <span class="char-card-name" :class="isNarrator(key) ? 'narrator' : 'dialogue'">{{ key }}</span>
              <span class="char-card-badge" :class="isNarrator(key) ? 'narrator' : 'dialogue'">
                {{ isNarrator(key) ? 'narrator' : 'dialogue' }}
              </span>
            </div>
            <div class="char-field">
              <div class="char-field-label">Voice profile</div>
              <input
                class="char-field-input"
                :value="profile.voice_profile"
                placeholder="e.g. deep, steady, ominous"
                @change="onProfileChange(key, ($event.target as HTMLInputElement).value)"
              />
            </div>
            <div class="char-field">
              <div class="char-field-label">Voice</div>
              <select
                class="char-field-input"
                :value="profile.voice_id || ''"
                @change="onVoiceChange(key, ($event.target as HTMLSelectElement).value)"
              >
                <option value="">Auto (best match)</option>
                <optgroup label="Male">
                  <option v-for="v in maleVoices" :key="v.voice_id" :value="v.voice_id">
                    {{ voiceLabel(v) }}
                  </option>
                </optgroup>
                <optgroup label="Female">
                  <option v-for="v in femaleVoices" :key="v.voice_id" :value="v.voice_id">
                    {{ voiceLabel(v) }}
                  </option>
                </optgroup>
              </select>
              <div v-if="!profile.voice_id" class="char-voice-hint">
                Matched automatically from voice profile when generating audio
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Segments -->
      <div class="segments-header">
        <h2>Segments</h2>
        <div class="segment-count">{{ script.segments.length }} segments</div>
      </div>
      <p class="click-hint">Tap a segment to edit it</p>

      <div class="segment-list">
        <div
          v-for="(seg, i) in script.segments"
          :key="i"
          class="segment-card"
          :class="{ editing: editingIndex === i }"
          @click="editingIndex !== i && toggleEdit(i)"
        >
          <div class="segment-top">
            <span class="segment-type" :class="`type-${seg.type}`">{{ seg.type }}</span>
            <span v-if="seg.character" class="segment-character">{{ seg.character }}</span>
            <span v-if="seg.tone && editingIndex !== i" class="segment-tone">{{ seg.tone }}</span>
            <span class="segment-index">#{{ i + 1 }}</span>
          </div>

          <!-- Display mode -->
          <template v-if="editingIndex !== i">
            <div v-if="isVoiceSegment(seg)" class="segment-text">{{ seg.text }}</div>
            <div v-else-if="isPauseSegment(seg)" class="segment-description">{{ seg.duration_ms || 1500 }}ms pause</div>
            <div v-else class="segment-description">{{ seg.description }}</div>
          </template>

          <!-- Edit mode -->
          <div v-if="editingIndex === i" class="segment-edit" @click.stop>
            <template v-if="isVoiceSegment(seg)">
              <textarea class="edit-field" v-model="editText" placeholder="Segment text"></textarea>
              <div class="edit-row">
                <input class="edit-field" v-model="editTone" placeholder="Tone (e.g. foreboding)" />
                <input class="edit-field" v-model="editCharacter" placeholder="Character" />
              </div>
            </template>
            <template v-else-if="isPauseSegment(seg)">
              <input class="edit-field" type="number" v-model.number="editDurationMs" placeholder="Duration (ms)" />
            </template>
            <template v-else>
              <textarea class="edit-field" v-model="editDescription" placeholder="Description"></textarea>
            </template>

            <div class="edit-actions">
              <button class="edit-btn edit-btn-save" @click="confirmEdit">Done</button>
              <button class="edit-btn edit-btn-cancel" @click="cancelEdit">Cancel</button>
              <button class="edit-btn edit-btn-delete" @click="deleteSegment(i)">Delete</button>
            </div>
          </div>
        </div>
      </div>
    </template>

    <div v-else class="empty-state">
      <p>No script found for this story.</p>
      <p>Generate a script from the <router-link :to="`/story/${storyId}`">story detail page</router-link>.</p>
    </div>
  </div>
</template>

<style scoped>
.back-link {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  color: var(--color-text-3);
  text-decoration: none;
  font-size: 0.8rem;
  padding: 0.5rem 0;
  transition: color 0.2s;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}
.back-link:hover { color: var(--color-text-2); }

.page-container { max-width: 720px; margin: 0 auto; padding: 1.25rem; }

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 1.25rem 0 1.75rem;
  border-bottom: 1px solid var(--color-border);
  margin-bottom: 1.25rem;
  gap: 1rem;
  flex-wrap: wrap;
}
.page-header h1 {
  font-family: var(--font-family-serif);
  font-size: 1.5rem;
  font-weight: 500;
  color: var(--color-text-1);
}
.page-header .subtitle {
  font-size: 0.8rem;
  color: var(--color-text-3);
  margin-top: 0.25rem;
  letter-spacing: 0.02em;
}

.save-btn {
  padding: 0.6rem 1.5rem;
  border: none;
  border-radius: var(--radius-sm);
  background: var(--color-accent);
  color: #fff;
  font-family: var(--font-family-sans);
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
  background: rgba(255,255,255,0.06);
  color: var(--color-text-3);
  cursor: not-allowed;
}

.save-status {
  font-size: 0.78rem; color: var(--color-text-3);
  text-align: right; margin-top: 0.3rem;
}
.save-status.error { color: #e07070; }
.save-status.success { color: var(--color-success); }

.regen-notice {
  margin-bottom: 1.5rem;
  padding: 0.75rem 1rem;
  background: rgba(255, 170, 0, 0.1);
  border-left: 3px solid var(--color-warn);
  border-radius: 4px;
  font-size: 0.9rem;
  color: var(--color-text-2);
}

/* ── Characters panel ────────────────────────── */
.characters-panel {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 1.1rem 1.3rem;
  margin-bottom: 1.25rem;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}
.characters-panel h2 {
  font-family: var(--font-family-serif);
  font-size: 1rem; font-weight: 500;
  color: var(--color-text-2);
  margin-bottom: 0.85rem; letter-spacing: 0.03em;
}
.character-list { display: flex; flex-direction: column; gap: 0.75rem; }
.character-card {
  background: rgba(0,0,0,0.2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 0.85rem 1rem;
}
.char-card-header {
  display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.65rem;
}
.char-card-name {
  font-family: var(--font-family-serif); font-size: 0.95rem; font-weight: 600;
}
.char-card-name.narrator { color: var(--color-success); }
.char-card-name.dialogue { color: var(--color-info); }
.char-card-badge {
  font-size: 0.6rem; font-weight: 600; text-transform: uppercase;
  padding: 0.12rem 0.4rem; border-radius: 4px; letter-spacing: 0.05em;
}
.char-card-badge.narrator { background: var(--color-success-dim); color: var(--color-success); }
.char-card-badge.dialogue { background: var(--color-info-dim); color: var(--color-info); }
.char-field { margin-bottom: 0.5rem; }
.char-field:last-child { margin-bottom: 0; }
.char-field-label {
  font-size: 0.65rem; color: var(--color-text-3);
  text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 0.25rem;
}
.char-field-input {
  width: 100%; padding: 0.45rem 0.65rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  color: var(--color-text-1);
  font-family: var(--font-family-sans);
  font-size: 0.8rem; outline: none;
  transition: border-color 0.2s;
}
.char-field-input:focus { border-color: var(--color-border-focus); }
select.char-field-input {
  cursor: pointer; color-scheme: dark;
  -webkit-appearance: none; appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' fill='%238a8a8a'%3E%3Cpath d='M2 4l4 4 4-4'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 0.65rem center;
  padding-right: 1.8rem;
}
select.char-field-input option,
select.char-field-input optgroup {
  background-color: var(--color-bg);
  color: var(--color-text-1);
}
.char-voice-hint {
  font-size: 0.68rem; color: var(--color-text-3);
  margin-top: 0.2rem; font-style: italic;
}

/* ── Segments list ───────────────────────────── */
.segments-header {
  display: flex; justify-content: space-between;
  align-items: center; margin-bottom: 0.85rem;
}
.segments-header h2 {
  font-family: var(--font-family-serif);
  font-size: 1.05rem; font-weight: 500;
  color: var(--color-text-1); letter-spacing: 0.03em;
}
.segment-count { font-size: 0.78rem; color: var(--color-text-3); }
.click-hint {
  font-size: 0.72rem; color: var(--color-text-3);
  text-align: center; margin-bottom: 1rem; letter-spacing: 0.03em;
}
.segment-list { display: flex; flex-direction: column; gap: 0.5rem; }
.segment-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 0.85rem 1rem;
  transition: all 0.2s;
  cursor: pointer;
}
.segment-card:hover { border-color: var(--color-border-hover); }
.segment-card.editing {
  border-color: var(--color-border-focus);
  background: var(--color-surface-hover);
  cursor: default;
}
.segment-top {
  display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.4rem;
}
.segment-type {
  font-size: 0.62rem; font-weight: 700; text-transform: uppercase;
  padding: 0.15rem 0.45rem; border-radius: 4px; letter-spacing: 0.05em;
}
.type-narration { background: var(--color-success-dim); color: var(--color-success); }
.type-dialogue { background: var(--color-info-dim); color: var(--color-info); }
.type-sfx { background: var(--color-warn-dim); color: var(--color-warn); }
.type-ambient { background: var(--color-ambient-dim); color: var(--color-ambient); }
.type-pause { background: var(--color-surface); color: var(--color-text-3); }
.segment-character { font-size: 0.78rem; color: var(--color-text-2); font-weight: 500; }
.segment-tone { font-size: 0.72rem; color: var(--color-text-3); font-style: italic; margin-left: auto; }
.segment-index { font-size: 0.68rem; color: var(--color-text-3); margin-left: auto; font-variant-numeric: tabular-nums; }
.segment-text { font-size: 0.82rem; color: var(--color-text-2); line-height: 1.5; word-break: break-word; }
.segment-description { font-size: 0.82rem; color: var(--color-text-3); font-style: italic; }

/* ── Inline edit ─────────────────────────────── */
.segment-edit {
  margin-top: 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.edit-field {
  width: 100%; padding: 0.5rem 0.7rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: rgba(0,0,0,0.2);
  color: var(--color-text-1);
  font-family: var(--font-family-sans);
  font-size: 0.82rem;
  resize: vertical; outline: none;
  transition: border-color 0.2s;
}
.edit-field:focus { border-color: var(--color-border-focus); }
textarea.edit-field { min-height: 60px; }
.edit-row { display: flex; gap: 0.5rem; }
.edit-row .edit-field { flex: 1; }
.edit-actions { display: flex; gap: 0.5rem; margin-top: 0.3rem; }
.edit-btn {
  padding: 0.35rem 0.85rem;
  border-radius: var(--radius-sm);
  font-family: var(--font-family-sans);
  font-size: 0.78rem;
  cursor: pointer; border: none;
  transition: all 0.2s; font-weight: 500;
}
.edit-btn-save { background: var(--color-success-dim); color: var(--color-success); }
.edit-btn-save:hover { background: rgba(58,125,92,0.2); }
.edit-btn-cancel { background: var(--color-surface); color: var(--color-text-2); }
.edit-btn-cancel:hover { background: var(--color-surface-hover); }
.edit-btn-delete { background: var(--color-error-dim); color: #e07070; }
.edit-btn-delete:hover { background: rgba(204,68,68,0.18); }

.empty-state { text-align: center; padding: 4rem 1rem; color: var(--color-text-3); }
.empty-state p { margin-top: 0.5rem; font-size: 0.9rem; }
.empty-state a { color: var(--color-accent); text-decoration: none; }
.empty-state a:hover { text-decoration: underline; }
</style>
