import { describe, expect, it } from 'vitest'
import {
  formatCount,
  formatLatency,
  formatLatencyAxis,
  formatPercent,
  formatRate,
  formatRelative,
  formatTime,
  NO_VALUE,
} from './format'

describe('formatLatency', () => {
  it.each([
    [0, '0.0 ms'],
    [0.01, '< 0.1 ms'],
    [0.34, '0.3 ms'],
    [4.24, '4.2 ms'],
    [9.94, '9.9 ms'],
    [9.96, '10 ms'],
    [842.4, '842 ms'],
    [999.4, '999 ms'],
    [999.6, '1.00 s'],
    [1240, '1.24 s'],
    [9994, '9.99 s'],
    [9996, '10.0 s'],
    [12_345, '12.3 s'],
  ])('%s ms -> %s', (ms, expected) => {
    expect(formatLatency(ms)).toBe(expected)
  })
})

describe('formatLatencyAxis', () => {
  it.each([
    [0, '0'],
    [0.5, '0.5 ms'],
    [250, '250 ms'],
    [1000, '1 s'],
    [1500, '1.5 s'],
    [12_000, '12 s'],
  ])('%s ms -> %s', (ms, expected) => {
    expect(formatLatencyAxis(ms)).toBe(expected)
  })
})

describe('formatPercent', () => {
  it.each([
    [0, '0.0 %'],
    [0.0001, '< 0.1 %'],
    [0.0005, '0.1 %'],
    [0.025, '2.5 %'],
    [0.1, '10.0 %'],
    [1, '100.0 %'],
  ])('%s -> %s', (fraction, expected) => {
    expect(formatPercent(fraction)).toBe(expected)
  })
})

describe('formatCount and formatRate', () => {
  it('groups thousands', () => {
    expect(formatCount(0)).toBe('0')
    expect(formatCount(12_345)).toBe('12,345')
  })

  it.each([
    [0, '0.0 req/min'],
    [8, '8.0 req/min'],
    [9.96, '10 req/min'],
    [1234.4, '1,234 req/min'],
  ])('%s per minute -> %s', (rate, expected) => {
    expect(formatRate(rate)).toBe(expected)
  })
})

// vite.config.ts runs tests in Asia/Kolkata (UTC+05:30), so these also prove the conversion from
// UTC to the viewer's zone.
describe('formatTime', () => {
  it('shows a UTC timestamp in local 24-hour time', () => {
    expect(formatTime('2026-09-30T10:04:05Z')).toBe('15:34:05')
    expect(formatTime('2026-09-30T14:30:00.250Z')).toBe('20:00:00')
  })

  it('accepts epoch milliseconds and can leave out seconds', () => {
    expect(formatTime(Date.UTC(2026, 8, 30, 18, 45, 59), { seconds: false })).toBe('00:15')
  })

  it.each([null, 'not a time'])('shows %j as no value', (value) => {
    expect(formatTime(value)).toBe(NO_VALUE)
  })
})

describe('formatRelative', () => {
  const now = Date.parse('2026-09-30T12:00:00Z')
  const secondsAgo = (seconds: number) => now - seconds * 1000

  it.each([
    [0, 'just now'],
    [4.9, 'just now'],
    [-30, 'just now'],
    [5, '5 s ago'],
    [59.9, '59 s ago'],
    [60, '1 min ago'],
    [3599, '59 min ago'],
    [3600, '1 h ago'],
    [26 * 3600, '26 h ago'],
  ])('%s s ago -> %s', (seconds, expected) => {
    expect(formatRelative(secondsAgo(seconds), now)).toBe(expected)
  })

  it('accepts an ISO timestamp', () => {
    expect(formatRelative('2026-09-30T11:58:00Z', now)).toBe('2 min ago')
  })
})

describe('null', () => {
  it('is shown as no value by every formatter, never as 0', () => {
    for (const format of [formatLatency, formatPercent, formatCount, formatRate]) {
      expect(format(null)).toBe(NO_VALUE)
    }
    expect(formatRelative(null, Date.now())).toBe(NO_VALUE)
  })
})
