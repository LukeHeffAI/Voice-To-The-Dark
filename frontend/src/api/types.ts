// ── Auth ──────────────────────────────────────────────

export interface User {
  id: number
  username: string
  is_admin: boolean
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: User
}

// ── Stories ───────────────────────────────────────────

export interface Story {
  id: number
  title: string
  author: string | null
  reddit_url: string | null
  narration_text: string | null
  content_hash: string
  audio_file_path: string | null
  part_count: number
  created_at: string | null
}

export interface StoryListItem {
  id: number
  title: string
  author: string | null
  reddit_url: string | null
  has_audio: boolean
  has_script: boolean
  part_count: number
  created_at: string | null
}

export interface TopNosleepPost {
  url: string
  title: string
  author: string
  score: number
  num_comments: number
  created_utc: number
  already_submitted: boolean
  is_series?: boolean
  gilded_count?: number
}

export interface DuplicateCheck {
  is_duplicate: boolean
  existing_story_id: number | null
  message: string
}

export interface FetchPreview {
  title: string
  author: string
  text: string
}

export interface PlaybackState {
  story_id: number
  user_id: number | null
  position_seconds: number
  updated_at: string | null
}

export interface Folder {
  id: number
  name: string
  story_count: number
  created_at: string | null
}

// ── Audio / Script ───────────────────────────────────

export interface CharacterProfile {
  voice_profile: string
  voice_id: string | null
}

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

export interface NarrationScript {
  title: string
  characters: Record<string, CharacterProfile>
  segments: ScriptSegment[]
}

export interface ScriptInfo {
  script: NarrationScript
  characters: string[]
  segment_count: number
  voice_segments: number
  sfx_segments: number
}

export interface CacheStats {
  total_segments: number
  cache_hits: number
  cache_misses: number
  api_calls_saved: number
}

export interface GenerateScriptResult {
  message: string
  script: NarrationScript
  characters: string[]
}

export interface GenerateNarrationResult {
  message: string
  audio_file: string
  segments_processed: number
  voice_assignments: Record<string, string>
  cache_stats: CacheStats
}

export interface GenerateAudioResult {
  message: string
  audio_file: string
}

// ── Player ───────────────────────────────────────────

export interface StoryInfo {
  id: number
  title: string
  author: string
  part_count: number
  has_audio: boolean
}

// ── Series ───────────────────────────────────────────

export interface SeriesPart {
  url: string
  title: string
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

// ── Playlist (frontend only) ─────────────────────────

export interface TrackInfo {
  storyId: number
  title: string
  author: string
}
