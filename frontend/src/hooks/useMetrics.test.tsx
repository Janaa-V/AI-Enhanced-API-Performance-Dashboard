import { act, waitFor } from '@testing-library/react'
import { delay, http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { findWindowPreset, type WindowPreset } from '../models/windows'
import { busyMetrics, emptyMetrics } from '../test/fixtures/metrics'
import { renderHookWithClient } from '../test/render'
import { METRICS_URL, metricsHandlers, server } from '../test/server'
import { metricsQueryKey, REFRESH_INTERVAL_MS, useMetrics } from './useMetrics'

const oneHour = findWindowPreset(60)!
const sixHours = findWindowPreset(360)!

// Answers busyMetrics for one hour and emptyMetrics otherwise, counting requests per window.
function countRequests() {
  const counts = new Map<string, number>()
  server.use(
    http.get(METRICS_URL, async ({ request }) => {
      const minutes = new URL(request.url).searchParams.get('window_minutes') ?? ''
      counts.set(minutes, (counts.get(minutes) ?? 0) + 1)
      await delay(10)
      return HttpResponse.json(minutes === '60' ? busyMetrics : emptyMetrics)
    }),
  )
  return (minutes: number) => counts.get(String(minutes)) ?? 0
}

function renderMetrics(preset: WindowPreset, autoRefresh = false) {
  return renderHookWithClient(
    (props: { preset: WindowPreset; autoRefresh: boolean }) =>
      useMetrics(props.preset, { autoRefresh: props.autoRefresh }),
    { preset, autoRefresh },
  )
}

afterEach(() => {
  vi.useRealTimers()
})

describe('useMetrics', () => {
  it('loads the metrics for the window', async () => {
    const { result } = renderMetrics(oneHour)
    expect(result.current.isPending).toBe(true)
    await waitFor(() => expect(result.current.data).toEqual(busyMetrics))
  })

  it('caches each window under its own key and keeps the old data while the new one loads', async () => {
    const requests = countRequests()
    const { result, rerender } = renderMetrics(oneHour)
    await waitFor(() => expect(result.current.data).toEqual(busyMetrics))

    rerender({ preset: sixHours, autoRefresh: false })
    expect(result.current).toMatchObject({ isPlaceholderData: true, data: busyMetrics })
    await waitFor(() => expect(result.current.data).toEqual(emptyMetrics))
    expect(result.current.isPlaceholderData).toBe(false)
    expect([requests(60), requests(360)]).toEqual([1, 1])
    expect(metricsQueryKey(oneHour)).not.toEqual(metricsQueryKey(sixHours))
  })

  it('polls only while auto-refresh is on', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const requests = countRequests()
    const { result, rerender } = renderMetrics(oneHour, true)
    await waitFor(() => expect(result.current.data).toBeDefined())
    expect(requests(60)).toBe(1)

    await act(() => vi.advanceTimersByTimeAsync(REFRESH_INTERVAL_MS))
    await waitFor(() => expect(requests(60)).toBe(2))

    rerender({ preset: oneHour, autoRefresh: false })
    await act(() => vi.advanceTimersByTimeAsync(REFRESH_INTERVAL_MS * 3))
    expect(requests(60)).toBe(2)
  })

  it('reports a rejected window preset on the console', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    server.use(metricsHandlers.validationError)
    const { result } = renderMetrics(oneHour)
    await waitFor(() => expect(result.current.error?.kind).toBe('validation'))
    expect(consoleError).toHaveBeenCalledWith(
      'GET /metrics rejected a window preset:',
      expect.stringMatching(/^Too many buckets/),
    )
  })
})
