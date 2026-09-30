import { act, renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { DEFAULT_WINDOW, findWindowPreset } from '../models/windows'
import { readControls, useDashboardControls, writeControls } from './useDashboardControls'

const sixHours = findWindowPreset(360)!

describe('readControls', () => {
  it('reads the window and auto-refresh from the query string', () => {
    expect(readControls('?window=360&refresh=off')).toEqual({
      preset: sixHours,
      autoRefresh: false,
    })
  })

  it.each(['', '?window=42', '?window=abc', '?refresh=maybe'])(
    'falls back to the defaults for %j',
    (search) => {
      expect(readControls(search)).toEqual({ preset: DEFAULT_WINDOW, autoRefresh: true })
    },
  )
})

describe('writeControls', () => {
  it('writes only what differs from the defaults', () => {
    expect(writeControls('', { preset: DEFAULT_WINDOW, autoRefresh: true })).toBe('')
    expect(writeControls('', { preset: sixHours, autoRefresh: false })).toBe(
      '?window=360&refresh=off',
    )
  })

  it('keeps unrelated parameters and removes defaults', () => {
    expect(
      writeControls('?debug=1&window=360', { preset: DEFAULT_WINDOW, autoRefresh: true }),
    ).toBe('?debug=1')
  })
})

describe('useDashboardControls', () => {
  it('starts from the URL and mirrors changes into it without adding history', () => {
    window.history.replaceState(null, '', '/?refresh=off')
    const historyLength = window.history.length
    const { result } = renderHook(() => useDashboardControls())
    expect(result.current).toMatchObject({ preset: DEFAULT_WINDOW, autoRefresh: false })

    act(() => result.current.setPreset(sixHours))
    expect(result.current.preset).toBe(sixHours)
    // The existing parameter keeps its place.
    expect(window.location.search).toBe('?refresh=off&window=360')

    act(() => result.current.setAutoRefresh(true))
    expect(window.location.search).toBe('?window=360')
    expect(window.history.length).toBe(historyLength)
  })
})
