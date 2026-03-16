import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useNotificationStore } from '../notifications'

describe('useNotificationStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })

  it('starts with empty messages', () => {
    const store = useNotificationStore()
    expect(store.messages).toEqual([])
  })

  it('show() adds a notification with auto-incrementing ID', () => {
    const store = useNotificationStore()
    store.show('Hello')
    store.show('World')

    expect(store.messages).toHaveLength(2)
    expect(store.messages[0]!.text).toBe('Hello')
    expect(store.messages[1]!.text).toBe('World')
    expect(store.messages[1]!.id).toBeGreaterThan(store.messages[0]!.id)
  })

  it('defaults to type "info"', () => {
    const store = useNotificationStore()
    store.show('Test')
    expect(store.messages[0]!.type).toBe('info')
  })

  it('accepts a custom type', () => {
    const store = useNotificationStore()
    store.show('Error!', 'error')
    expect(store.messages[0]!.type).toBe('error')

    store.show('Success!', 'success')
    expect(store.messages[1]!.type).toBe('success')
  })

  it('dismiss() removes a notification by ID', () => {
    const store = useNotificationStore()
    store.show('Keep')
    store.show('Remove')
    const removeId = store.messages[1]!.id

    store.dismiss(removeId)

    expect(store.messages).toHaveLength(1)
    expect(store.messages[0]!.text).toBe('Keep')
  })

  it('auto-dismisses after the default timeout (4000ms)', () => {
    const store = useNotificationStore()
    store.show('Auto-dismiss')

    expect(store.messages).toHaveLength(1)

    vi.advanceTimersByTime(4000)

    expect(store.messages).toHaveLength(0)
  })

  it('auto-dismisses after a custom timeout', () => {
    const store = useNotificationStore()
    store.show('Quick', 'info', 1000)

    vi.advanceTimersByTime(999)
    expect(store.messages).toHaveLength(1)

    vi.advanceTimersByTime(1)
    expect(store.messages).toHaveLength(0)
  })

  it('does not auto-dismiss when timeout is 0', () => {
    const store = useNotificationStore()
    store.show('Permanent', 'error', 0)

    vi.advanceTimersByTime(10000)
    expect(store.messages).toHaveLength(1)
  })
})
