import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import TaskProgressBar from '../TaskProgressBar.vue'
import type { TaskStatus } from '@/types'

function makeTask(overrides: Partial<TaskStatus> = {}): TaskStatus {
  return {
    task_id: 1,
    task_type: 'generate_narration',
    status: 'generating_segments',
    progress_current: 5,
    progress_total: 10,
    progress_message: 'Generating segments...',
    result_data: null,
    error_message: '',
    created_at: '2026-01-01T00:00:00Z',
    started_at: '2026-01-01T00:00:01Z',
    completed_at: null,
    ...overrides,
  }
}

describe('TaskProgressBar', () => {
  it('renders nothing when task is null', () => {
    const wrapper = mount(TaskProgressBar, { props: { task: null } })
    expect(wrapper.find('.task-progress').exists()).toBe(false)
  })

  it('renders progress message', () => {
    const wrapper = mount(TaskProgressBar, {
      props: { task: makeTask({ progress_message: 'Processing...' }) },
    })
    expect(wrapper.find('.progress-message').text()).toBe('Processing...')
  })

  it('computes percentage correctly', () => {
    const wrapper = mount(TaskProgressBar, {
      props: { task: makeTask({ progress_current: 3, progress_total: 10 }) },
    })
    expect(wrapper.find('.progress-percent').text()).toBe('30%')
  })

  it('shows 100% when complete', () => {
    const wrapper = mount(TaskProgressBar, {
      props: { task: makeTask({ progress_current: 10, progress_total: 10, status: 'complete' }) },
    })
    expect(wrapper.find('.progress-percent').text()).toBe('100%')
  })

  it('shows indeterminate for queued status', () => {
    const wrapper = mount(TaskProgressBar, {
      props: { task: makeTask({ status: 'queued', progress_total: 0 }) },
    })
    expect(wrapper.find('.progress-bar-fill').classes()).toContain('indeterminate')
    expect(wrapper.find('.progress-percent').exists()).toBe(false)
  })

  it('shows indeterminate when total is 0', () => {
    const wrapper = mount(TaskProgressBar, {
      props: { task: makeTask({ progress_total: 0 }) },
    })
    expect(wrapper.find('.progress-bar-fill').classes()).toContain('indeterminate')
  })

  it('shows determinate progress bar with width style', () => {
    const wrapper = mount(TaskProgressBar, {
      props: { task: makeTask({ progress_current: 7, progress_total: 10, status: 'generating_segments' }) },
    })
    const fill = wrapper.find('.progress-bar-fill')
    expect(fill.classes()).not.toContain('indeterminate')
    expect(fill.attributes('style')).toContain('width: 70%')
  })
})
