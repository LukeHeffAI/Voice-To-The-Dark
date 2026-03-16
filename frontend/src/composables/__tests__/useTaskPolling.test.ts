import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { ref } from 'vue'

// Mock vue's onUnmounted since we're not in a component context
vi.mock('vue', async () => {
  const actual = await vi.importActual('vue')
  return {
    ...actual,
    onUnmounted: vi.fn(),
  }
})

// Mock the API client
vi.mock('@/api/client', () => ({
  tasksApi: {
    getStatus: vi.fn(),
  },
}))

import { tasksApi } from '@/api/client'
import { useTaskPolling } from '../useTaskPolling'

describe('useTaskPolling', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('starts polling and updates task ref', async () => {
    vi.mocked(tasksApi.getStatus).mockResolvedValue({
      id: 1,
      status: 'processing',
      progress_current: 1,
      progress_total: 10,
      progress_message: 'Working...',
    })

    const { task, isPolling, startPolling } = useTaskPolling()

    await startPolling(1)

    expect(isPolling.value).toBe(true)
    expect(task.value).not.toBeNull()
    expect(task.value!.status).toBe('processing')
  })

  it('stops polling when task completes', async () => {
    vi.mocked(tasksApi.getStatus).mockResolvedValue({
      id: 1,
      status: 'complete',
      progress_current: 10,
      progress_total: 10,
      progress_message: 'Done',
    })

    const onComplete = vi.fn()
    const { isPolling, startPolling } = useTaskPolling()

    await startPolling(1, onComplete)

    expect(isPolling.value).toBe(false)
    expect(onComplete).toHaveBeenCalledOnce()
  })

  it('stops polling when task fails', async () => {
    vi.mocked(tasksApi.getStatus).mockResolvedValue({
      id: 1,
      status: 'failed',
      progress_current: 0,
      progress_total: 0,
      progress_message: 'Error',
      error_message: 'Something broke',
    })

    const onComplete = vi.fn()
    const { isPolling, startPolling } = useTaskPolling()

    await startPolling(1, onComplete)

    expect(isPolling.value).toBe(false)
    expect(onComplete).toHaveBeenCalledOnce()
  })

  it('stops polling on API error', async () => {
    vi.mocked(tasksApi.getStatus).mockRejectedValue(new Error('Network error'))

    const { isPolling, startPolling } = useTaskPolling()

    await startPolling(1)

    expect(isPolling.value).toBe(false)
  })

  it('stopPolling clears timer', async () => {
    let callCount = 0
    vi.mocked(tasksApi.getStatus).mockImplementation(async () => {
      callCount++
      return {
        id: 1,
        status: 'processing',
        progress_current: callCount,
        progress_total: 10,
        progress_message: 'Working...',
      }
    })

    const { stopPolling, startPolling } = useTaskPolling()

    await startPolling(1)
    stopPolling()

    const countBefore = callCount
    vi.advanceTimersByTime(5000)
    // No new calls after stop
    expect(callCount).toBe(countBefore)
  })
})
