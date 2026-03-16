// ── API response types ──────────────────────────────────────

export interface User {
  id: number
  username: string
  is_admin: boolean
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: User
}

export interface Story {
  id: number
  title: string
  author: string | null
  reddit_url: string | null
  narration_text: string | null
  content_hash: string
  audio_file_path: string | null
  part_count: number
  created_at: string
}

export interface StoryListItem {
  id: number
  title: string
  author: string | null
  reddit_url: string | null
  has_audio: boolean
  has_script: boolean
  part_count: number
  created_at: string
}

export interface Folder {
  id: number
  name: string
  story_count: number
  created_at: string
}

export interface TopPost {
  url: string
  title: string
  author: string
  created_utc: number
  already_submitted: boolean
  score?: number
  num_comments?: number
  gilded?: number
}

export interface FetchPreview {
  title: string
  author: string
  text: string
}

export interface DuplicateCheck {
  is_duplicate: boolean
  existing_story_id: number | null
  message: string
}

export interface SeriesPart {
  title: string
  url: string
  author: string
  created_utc: number
  story_id: number | null
}

export interface SeriesPartsResponse {
  parts: SeriesPart[]
  series_word_count: number
  series_est_minutes: number
  submitted_count: number
  total_count: number
}

export interface PlaybackState {
  story_id: number
  user_id: number | null
  position_seconds: number
  updated_at: string | null
}

// ── Script types ────────────────────────────────────────────

export type SegmentType = 'narration' | 'dialogue' | 'sfx' | 'ambient' | 'pause'

export interface ScriptSegment {
  type: SegmentType
  character?: string
  text?: string
  tone?: string
  description?: string
  duration_ms?: number
  loop?: boolean
}

export interface CharacterDef {
  voice_profile: string
  voice_id: string | null
}

export interface NarrationScript {
  title: string
  characters: Record<string, CharacterDef>
  segments: ScriptSegment[]
}

export interface GenerateScriptResponse {
  message: string
  script: NarrationScript
  characters: string[]
}

export interface ScriptInfoResponse {
  script: NarrationScript
  characters: string[]
  segment_count: number
  voice_segments: number
  sfx_segments: number
}

export interface GenerateNarrationResponse {
  message: string
  audio_file: string
  segments_processed: number
  voice_assignments: Record<string, string>
  cache_stats: {
    total_segments: number
    cache_hits: number
    cache_misses: number
    api_calls_saved: number
  }
}

// ── Settings types ──────────────────────────────────────────

export interface VoiceEntry {
  voice_id: string
  name: string
  gender: string
  age: string
  archetypes: string[]
  role: string
}

export interface StoryInfo {
  id: number
  title: string
  author: string
  part_count: number
  has_audio: boolean
}

// ── Player / Playlist types ─────────────────────────────────

export interface PlaylistItem {
  storyId: number
  title: string
  author: string
}

export type RepeatMode = 'off' | 'all' | 'one'

export type ToastType = 'info' | 'success' | 'error' | 'warn'

export interface Toast {
  id: number
  message: string
  type: ToastType
  timeout: number
}
