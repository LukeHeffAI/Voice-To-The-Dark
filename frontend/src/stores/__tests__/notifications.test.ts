import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useNotificationStore } from '../notifications'

describe('Notifications Store', () => {
  let store: ReturnType<typeof useNotificationStore>

  beforeEach(() => {
    vi.useFakeTimers()
    setActivePinia(createPinia())
    store = useNotificationStore()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('show', () => {
    it('adds a toast with auto-increment ID', () => {
      store.show('Hello')
      store.show('World')
      expect(store.toasts).toHaveLength(2)
      expect(store.toasts[0].id).not.toBe(store.toasts[1].id)
    })

    it('sets default type to info', () => {
      store.show('Test message')
      expect(store.toasts[0].type).toBe('info')
    })

    it('accepts custom type', () => {
      store.show('Error!', 'error')
      expect(store.toasts[0].type).toBe('error')
    })

    it('sets default timeout of 3000ms', () => {
      store.show('Test')
      expect(store.toasts[0].timeout).toBe(3000)
    })

    it('accepts custom timeout', () => {
      store.show('Test', 'info', 5000)
      expect(store.toasts[0].timeout).toBe(5000)
    })

    it('auto-dismisses after timeout', () => {
      store.show('Auto dismiss', 'info', 3000)
      expect(store.toasts).toHaveLength(1)
      vi.advanceTimersByTime(3000)
      expect(store.toasts).toHaveLength(0)
    })

    it('does not auto-dismiss with timeout 0', () => {
      store.show('Persistent', 'info', 0)
      vi.advanceTimersByTime(10000)
      expect(store.toasts).toHaveLength(1)
    })
  })

  describe('dismiss', () => {
    it('removes the correct toast by ID', () => {
      store.show('First')
      store.show('Second')
      const firstId = store.toasts[0].id
      store.dismiss(firstId)
      expect(store.toasts).toHaveLength(1)
      expect(store.toasts[0].message).toBe('Second')
    })

    it('does nothing for non-existent ID', () => {
      store.show('Test')
      store.dismiss(99999)
      expect(store.toasts).toHaveLength(1)
    })
  })
})
