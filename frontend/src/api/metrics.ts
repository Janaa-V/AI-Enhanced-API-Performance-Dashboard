import type { MetricsQuery, MetricsResponse } from '../models/metrics'
import { apiClient } from './client'

export interface MetricsParams {
  windowMinutes: number
  bucketMinutes: number
  // Omitted: the backend's default (20).
  recentLimit?: number
}

// GET /metrics. Resolves with one snapshot, rejects with an ApiError, or with Axios's
// CanceledError when `signal` aborts.
export async function fetchMetrics(
  { windowMinutes, bucketMinutes, recentLimit }: MetricsParams,
  signal?: AbortSignal,
): Promise<MetricsResponse> {
  // Typed against the contract, so a renamed backend parameter is a compile error here.
  const params: MetricsQuery = {
    window_minutes: windowMinutes,
    bucket_minutes: bucketMinutes,
    recent_limit: recentLimit,
  }
  const response = await apiClient.get<MetricsResponse>('/metrics', { params, signal })
  return response.data
}
