import { describe, it, expect } from 'vitest'
import { formatTime } from '../useFormatTime'

describe('formatTime', () => {
  it('formats 0 seconds as "0:00"', () => {
    expect(formatTime(0)).toBe('0:00')
  })

  it('formats seconds under a minute', () => {
    expect(formatTime(45)).toBe('0:45')
  })

  it('formats exact minutes', () => {
    expect(formatTime(60)).toBe('1:00')
    expect(formatTime(120)).toBe('2:00')
  })

  it('formats minutes and seconds', () => {
    expect(formatTime(65)).toBe('1:05')
    expect(formatTime(754)).toBe('12:34')
  })

  it('formats hours with padded minutes', () => {
    expect(formatTime(3600)).toBe('1:00:00')
    expect(formatTime(3661)).toBe('1:01:01')
    expect(formatTime(7384)).toBe('2:03:04')
  })

  it('handles NaN as "0:00"', () => {
    expect(formatTime(NaN)).toBe('0:00')
  })

  it('handles Infinity as "0:00"', () => {
    expect(formatTime(Infinity)).toBe('0:00')
    expect(formatTime(-Infinity)).toBe('0:00')
  })

  it('handles negative values as "0:00"', () => {
    expect(formatTime(-5)).toBe('0:00')
    expect(formatTime(-100)).toBe('0:00')
  })

  it('truncates fractional seconds', () => {
    expect(formatTime(65.9)).toBe('1:05')
  })
})
