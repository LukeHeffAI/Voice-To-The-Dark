import { request } from './client'
import type {
  DuplicateCheck,
  FetchPreview,
  Folder,
  PlaybackState,
  SeriesPartsResponse,
  Story,
  StoryListItem,
  TopNosleepPost,
} from './types'

export function listStories(skip = 0, limit = 25) {
  return request<StoryListItem[]>('GET', '/stories/', {
    params: { skip: String(skip), limit: String(limit) },
  })
}

export function getStory(id: number) {
  return request<Story>('GET', `/stories/${id}`)
}

export function submitStory(reddit_url: string) {
  return request<Story>('POST', '/stories/submit', {
    body: { reddit_url },
  })
}

export function submitManual(data: {
  title?: string
  author?: string
  text_content?: string
  reddit_url?: string
}) {
  return request<Story>('POST', '/stories/submit-manual', { body: data })
}

export function topNosleep(timeframe = 'alltime', limit = 50) {
  return request<TopNosleepPost[]>('GET', '/stories/top-nosleep', {
    params: { timeframe, limit: String(limit) },
  })
}

export function fetchPreview(reddit_url: string, signal?: AbortSignal) {
  return request<FetchPreview>('GET', '/stories/fetch-preview', {
    params: { reddit_url },
    signal,
  })
}

export function checkDuplicate(reddit_url: string) {
  return request<DuplicateCheck>('GET', '/stories/check-duplicate/', {
    params: { reddit_url },
  })
}

export function hideStory(storyId: number) {
  return request<{ ok: boolean }>('POST', `/stories/${storyId}/hide`)
}

export function unhideStory(storyId: number) {
  return request<{ ok: boolean }>('POST', `/stories/${storyId}/unhide`)
}

export function getSeriesParts(storyId: number) {
  return request<SeriesPartsResponse>('GET', `/stories/${storyId}/series-parts`)
}

// ── Playback ─────────────────────────────────────────

export function savePlayback(storyId: number, positionSeconds: number) {
  return request<PlaybackState>('POST', '/stories/playback', {
    body: { story_id: storyId, position_seconds: positionSeconds },
  })
}

export function getPlayback(storyId: number) {
  return request<PlaybackState>('GET', `/stories/playback/${storyId}`)
}

// ── Folders ──────────────────────────────────────────

export function listFolders() {
  return request<Folder[]>('GET', '/stories/folders/list')
}

export function createFolder(name: string) {
  return request<Folder>('POST', '/stories/folders/create', {
    body: { name },
  })
}

export function deleteFolder(folderId: number) {
  return request<{ ok: boolean }>('DELETE', `/stories/folders/${folderId}`)
}

export function addStoryToFolder(folderId: number, storyId: number) {
  return request<{ ok: boolean; message: string }>('POST', `/stories/folders/${folderId}/add`, {
    body: { story_id: storyId },
  })
}

export function removeStoryFromFolder(folderId: number, storyId: number) {
  return request<{ ok: boolean }>(
    'DELETE',
    `/stories/folders/${folderId}/stories/${storyId}`,
  )
}
