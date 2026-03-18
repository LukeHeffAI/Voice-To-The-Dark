import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import ToastContainer from '../ToastContainer.vue'
import { useNotificationStore } from '@/stores/notifications'

describe('ToastContainer', () => {
  let notify: ReturnType<typeof useNotificationStore>

  beforeEach(() => {
    vi.useFakeTimers()
    setActivePinia(createPinia())
    notify = useNotificationStore()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders no toasts initially', () => {
    const wrapper = mount(ToastContainer)
    expect(wrapper.findAll('.toast-item')).toHaveLength(0)
  })

  it('renders toast messages', () => {
    notify.show('Hello World', 'info', 0)
    const wrapper = mount(ToastContainer)
    expect(wrapper.findAll('.toast-item')).toHaveLength(1)
    expect(wrapper.find('.toast-item').text()).toBe('Hello World')
  })

  it('renders multiple toasts', () => {
    notify.show('First', 'info', 0)
    notify.show('Second', 'error', 0)
    const wrapper = mount(ToastContainer)
    expect(wrapper.findAll('.toast-item')).toHaveLength(2)
  })

  it('applies type-based CSS class', () => {
    notify.show('Error message', 'error', 0)
    const wrapper = mount(ToastContainer)
    expect(wrapper.find('.toast-item').classes()).toContain('toast-error')
  })

  it('dismisses toast on click', async () => {
    notify.show('Click me', 'info', 0)
    const wrapper = mount(ToastContainer)
    await wrapper.find('.toast-item').trigger('click')
    expect(notify.toasts).toHaveLength(0)
  })
})
