import { request, uploadFile } from './client'

export function getSettings() {
  return request<Record<string, string>>('GET', '/settings/')
}

export function updateSettings(body: Record<string, string | number>) {
  return request<{ updated: Record<string, string> }>('PUT', '/settings/', { body })
}

export function uploadRedditCache(timeframe: string, file: File) {
  const formData = new FormData()
  formData.append('timeframe', timeframe)
  formData.append('file', file)
  return uploadFile<{ status: string; timeframe: string; posts_count: number }>(
    `/settings/upload-reddit-cache?timeframe=${encodeURIComponent(timeframe)}`,
    formData,
  )
}

export function getVoiceNotes() {
  return request<Record<string, string>>('GET', '/settings/voice-notes')
}

export function updateVoiceNotes(notes: Record<string, string>) {
  return request<{ notes: Record<string, string> }>('PUT', '/settings/voice-notes', {
    body: notes,
  })
}

/** Returns the preview audio URL for the given voice. */
export function voicePreviewUrl(voiceId: string): string {
  return `/api/settings/voice-preview/${voiceId}`
}
