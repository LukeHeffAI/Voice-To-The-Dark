import { request } from './client'
import type {
  GenerateAudioResult,
  GenerateNarrationResult,
  GenerateScriptResult,
  NarrationScript,
  ScriptInfo,
} from './types'

export function generateScript(storyId: number, forceRegenerate = false) {
  return request<GenerateScriptResult>('POST', '/audio/generate-script', {
    body: { story_id: storyId, force_regenerate: forceRegenerate },
  })
}

export function generateAudio(storyId: number, voiceId: string, forceRegenerate = false) {
  return request<GenerateAudioResult>('POST', '/audio/generate-audio', {
    body: { story_id: storyId, voice_id: voiceId, force_regenerate: forceRegenerate },
  })
}

export function generateNarration(
  storyId: number,
  opts?: {
    voice_map?: Record<string, string>
    force_regenerate?: boolean
    bust_cache?: boolean
  },
) {
  return request<GenerateNarrationResult>('POST', '/audio/generate-narration', {
    body: {
      story_id: storyId,
      voice_map: opts?.voice_map ?? null,
      force_regenerate: opts?.force_regenerate ?? false,
      bust_cache: opts?.bust_cache ?? false,
    },
  })
}

export function getScript(storyId: number) {
  return request<ScriptInfo>('GET', `/audio/script/${storyId}`)
}

export function updateScript(storyId: number, script: NarrationScript) {
  return request<{ message: string; characters: string[] }>(
    'PUT',
    `/audio/script/${storyId}`,
    { body: script },
  )
}
