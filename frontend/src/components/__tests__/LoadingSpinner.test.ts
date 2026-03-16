import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import LoadingSpinner from '../LoadingSpinner.vue'

describe('LoadingSpinner', () => {
  it('renders a spinner element', () => {
    const wrapper = mount(LoadingSpinner)
    expect(wrapper.find('.spinner').exists()).toBe(true)
  })

  it('defaults to small size', () => {
    const wrapper = mount(LoadingSpinner)
    expect(wrapper.find('.spinner').classes()).not.toContain('spinner-lg')
  })

  it('applies large class when size is lg', () => {
    const wrapper = mount(LoadingSpinner, { props: { size: 'lg' } })
    expect(wrapper.find('.spinner').classes()).toContain('spinner-lg')
  })

  it('does not apply large class when size is sm', () => {
    const wrapper = mount(LoadingSpinner, { props: { size: 'sm' } })
    expect(wrapper.find('.spinner').classes()).not.toContain('spinner-lg')
  })
})
