import { describe, expect, it } from 'vitest'
import { DEFAULT_WINDOW, findWindowPreset, LIMITS, WINDOW_PRESETS } from './windows'

describe('WINDOW_PRESETS', () => {
  it.each(WINDOW_PRESETS)('$label stays within the backend limits', (preset) => {
    const { windowMinutes, bucketMinutes } = preset
    expect(windowMinutes).toBeGreaterThanOrEqual(1)
    expect(windowMinutes).toBeLessThanOrEqual(LIMITS.maxWindowMinutes)
    expect(bucketMinutes).toBeGreaterThanOrEqual(1)
    expect(bucketMinutes).toBeLessThanOrEqual(LIMITS.maxBucketMinutes)
    expect(windowMinutes / bucketMinutes).toBeLessThanOrEqual(LIMITS.maxBuckets)
    // Whole buckets only, so the chart's buckets are all the same width.
    expect(windowMinutes % bucketMinutes).toBe(0)
  })

  it('lists each window once, shortest first', () => {
    const minutes = WINDOW_PRESETS.map((preset) => preset.windowMinutes)
    expect(minutes).toEqual([...new Set(minutes)].sort((a, b) => a - b))
  })

  it('defaults to one hour', () => {
    expect(DEFAULT_WINDOW).toMatchObject({ windowMinutes: 60, bucketMinutes: 5 })
  })
})

describe('findWindowPreset', () => {
  it('finds a preset by its window length', () => {
    expect(findWindowPreset(360)?.label).toBe('6 hours')
  })

  it('returns undefined for a length no preset offers', () => {
    expect(findWindowPreset(42)).toBeUndefined()
  })
})
