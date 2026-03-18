import { request } from './client'
import type { StoryInfo } from './types'

export function getStoryInfo(storyId: number) {
  return request<StoryInfo>('GET', `/player/story-info/${storyId}`)
}

/** Returns the streaming URL for the given story. Used as audio src. */
export function streamUrl(storyId: number): string {
  return `/api/player/stream/${storyId}`
}

/** Returns the download URL for the given story. Used as <a> href. */
export function downloadUrl(storyId: number): string {
  return `/api/player/download/${storyId}`
}
