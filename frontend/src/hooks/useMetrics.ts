import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import { fetchMetrics } from '../api/metrics'
import type { WindowPreset } from '../models/windows'

export const REFRESH_INTERVAL_MS = 15_000

export function metricsQueryKey({ windowMinutes, bucketMinutes }: WindowPreset) {
  return ['metrics', windowMinutes, bucketMinutes] as const
}

// The one GET /metrics query. Every panel renders from its single response, so they always
// describe the same snapshot.
export function useMetrics(preset: WindowPreset, { autoRefresh }: { autoRefresh: boolean }) {
  const query = useQuery({
    queryKey: metricsQueryKey(preset),
    // The signal lets TanStack Query cancel a request that is no longer needed.
    queryFn: ({ signal }) => fetchMetrics(preset, signal),
    // TanStack Query pauses the interval while the tab is hidden and refetches on focus.
    refetchInterval: autoRefresh ? REFRESH_INTERVAL_MS : false,
    // While another window loads, keep showing the last one instead of a blank page.
    placeholderData: keepPreviousData,
  })

  // A 422 means a preset breaks the backend's limits: a bug to fix, not a user error.
  const { error } = query
  useEffect(() => {
    if (error?.kind === 'validation') {
      console.error('GET /metrics rejected a window preset:', error.message)
    }
  }, [error])

  return query
}
