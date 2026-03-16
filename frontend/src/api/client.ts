import type {
  User,
  LoginResponse,
  Story,
  StoryListItem,
  Folder,
  TopPost,
  FetchPreview,
  DuplicateCheck,
  SeriesPartsResponse,
  PlaybackState,
  GenerateScriptResponse,
  ScriptInfoResponse,
  GenerateNarrationResponse,
  NarrationScript,
  VoiceEntry,
  StoryInfo,
} from '@/types'

// ── Low-level fetch wrapper ─────────────────────────────────

function getToken(): string | null {
  try {
    const raw = localStorage.getItem('auth')
    if (raw) {
      const parsed = JSON.parse(raw)
      return parsed?.token ?? null
    }
  } catch {
    /* ignore */
  }
  return null
}

class ApiError extends Error {
  constructor(
    public status: number,
    public body: unknown,
  ) {
    super(`API error ${status}`)
    this.name = 'ApiError'
  }
}

async function request<T>(method: string, path: string, body?: unknown, multipart?: boolean): Promise<T> {
  const headers: Record<string, string> = {}
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`

  let fetchBody: BodyInit | undefined
  if (multipart && body instanceof FormData) {
    fetchBody = body
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    fetchBody = JSON.stringify(body)
  }

  const res = await fetch(`/api${path}`, { method, headers, body: fetchBody, credentials: 'same-origin' })

  if (res.status === 401) {
    // Clear stored token and redirect to login
    localStorage.removeItem('auth')
    if (window.location.pathname !== '/login') {
      window.location.href = '/login'
    }
    throw new ApiError(401, 'Unauthorized')
  }

  if (!res.ok) {
    let errorBody: unknown
    try {
      errorBody = await res.json()
    } catch {
      errorBody = await res.text()
    }
    throw new ApiError(res.status, errorBody)
  }

  // Handle empty responses
  const text = await res.text()
  if (!text) return undefined as T
  return JSON.parse(text) as T
}

// ── Typed API methods ───────────────────────────────────────

export const authApi = {
  login: (username: string, password: string) =>
    request<LoginResponse>('POST', '/auth/login', { username, password }),
  logout: () => request<{ message: string }>('POST', '/auth/logout'),
  me: () => request<User>('GET', '/auth/me'),
  register: (username: string, password: string) =>
    request<User>('POST', '/auth/register', { username, password }),
}

export const storiesApi = {
  list: (skip = 0, limit = 25) =>
    request<StoryListItem[]>('GET', `/stories/?skip=${skip}&limit=${limit}`),
  get: (id: number) => request<Story>('GET', `/stories/${id}`),
  submit: (reddit_url: string) =>
    request<Story>('POST', '/stories/submit', { reddit_url }),
  submitManual: (data: { title?: string; author?: string; text_content?: string; reddit_url?: string }) =>
    request<Story>('POST', '/stories/submit-manual', data),
  topNosleep: (timeframe = 'alltime', limit = 50) =>
    request<TopPost[]>('GET', `/stories/top-nosleep?timeframe=${timeframe}&limit=${limit}`),
  fetchPreview: (reddit_url: string) =>
    request<FetchPreview>('GET', `/stories/fetch-preview?reddit_url=${encodeURIComponent(reddit_url)}`),
  checkDuplicate: (reddit_url: string) =>
    request<DuplicateCheck>('GET', `/stories/check-duplicate/?reddit_url=${encodeURIComponent(reddit_url)}`),
  hide: (id: number) => request<{ ok: boolean }>('POST', `/stories/${id}/hide`),
  unhide: (id: number) => request<{ ok: boolean }>('POST', `/stories/${id}/unhide`),
  seriesParts: (id: number) =>
    request<SeriesPartsResponse>('GET', `/stories/${id}/series-parts`),
  savePlayback: (story_id: number, position_seconds: number) =>
    request<PlaybackState>('POST', '/stories/playback', { story_id, position_seconds }),
  getPlayback: (story_id: number) =>
    request<PlaybackState>('GET', `/stories/playback/${story_id}`),
}

export const foldersApi = {
  list: () => request<Folder[]>('GET', '/stories/folders/list'),
  create: (name: string) => request<Folder>('POST', '/stories/folders/create', { name }),
  delete: (id: number) => request<{ ok: boolean }>('DELETE', `/stories/folders/${id}`),
  addStory: (folderId: number, storyId: number) =>
    request<{ ok: boolean; message: string }>('POST', `/stories/folders/${folderId}/add`, { story_id: storyId }),
  removeStory: (folderId: number, storyId: number) =>
    request<{ ok: boolean }>('DELETE', `/stories/folders/${folderId}/stories/${storyId}`),
}

export const audioApi = {
  generateScript: (story_id: number, force_regenerate = false) =>
    request<GenerateScriptResponse>('POST', '/audio/generate-script', { story_id, force_regenerate }),
  getScript: (story_id: number) =>
    request<ScriptInfoResponse>('GET', `/audio/script/${story_id}`),
  updateScript: (story_id: number, script: NarrationScript) =>
    request<{ message: string; characters: string[] }>('PUT', `/audio/script/${story_id}`, script),
  generateAudio: (story_id: number, voice_id: string, force_regenerate = false) =>
    request<{ message: string; audio_file: string }>('POST', '/audio/generate-audio', {
      story_id,
      voice_id,
      force_regenerate,
    }),
  generateNarration: (
    story_id: number,
    voice_map?: Record<string, string> | null,
    force_regenerate = false,
    bust_cache = false,
  ) =>
    request<GenerateNarrationResponse>('POST', '/audio/generate-narration', {
      story_id,
      voice_map,
      force_regenerate,
      bust_cache,
    }),
}

export const settingsApi = {
  get: () => request<Record<string, string>>('GET', '/settings/api'),
  update: (data: Record<string, unknown>) =>
    request<{ updated: Record<string, string> }>('PUT', '/settings/api', data),
  voiceNotes: () => request<Record<string, string>>('GET', '/settings/voice-notes'),
  updateVoiceNotes: (notes: Record<string, string>) =>
    request<{ notes: Record<string, string> }>('PUT', '/settings/voice-notes', notes),
  voicePreviewUrl: (voiceId: string) => `/api/settings/voice-preview/${voiceId}`,
  uploadRedditCache: (timeframe: string, file: File) => {
    const form = new FormData()
    form.append('timeframe', timeframe)
    form.append('file', file)
    return request<{ status: string; timeframe: string; posts_count: number }>(
      'POST',
      '/settings/upload-reddit-cache',
      form,
      true,
    )
  },
  voices: () => request<VoiceEntry[]>('GET', '/settings/voices'),
}

export const playerApi = {
  storyInfo: (id: number) => request<StoryInfo>('GET', `/player/story-info/${id}`),
  streamUrl: (id: number) => `/api/player/stream/${id}`,
  downloadUrl: (id: number) => `/api/player/download/${id}`,
}

export { ApiError }
