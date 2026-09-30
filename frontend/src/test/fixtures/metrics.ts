// Typed GET /metrics responses for tests. Each is internally consistent, as the backend's would
// be: endpoint and bucket counts add up to the summary, and status codes add up to the total.
import type { MetricsResponse, TrendBucket } from '../../models/metrics'

type Stats = Omit<TrendBucket, 'start' | 'end'>

// Error rate and nulls follow the backend's rules: no requests means null, never 0.
function stats(
  total: number,
  serverErrors: number,
  clientErrors: number,
  avgLatencyMs: number | null = null,
  p95LatencyMs: number | null = null,
): Stats {
  return {
    total_requests: total,
    server_errors: serverErrors,
    client_errors: clientErrors,
    error_rate: total === 0 ? null : serverErrors / total,
    avg_latency_ms: avgLatencyMs,
    p95_latency_ms: p95LatencyMs,
  }
}

// A 15-minute window in 5-minute buckets, starting 2026-09-30 10:00 UTC.
const at = (minute: number) => `2026-09-30T10:${String(minute).padStart(2, '0')}:00Z`
const fifteenMinutes = { start: at(0), end: at(15), window_minutes: 15, bucket_minutes: 5 }

function buckets(perBucket: Stats[]): TrendBucket[] {
  return perBucket.map((bucket, index) => ({
    start: at(index * 5),
    end: at(index * 5 + 5),
    ...bucket,
  }))
}

// 120 requests: GET /demo/users is fast and healthy; POST /demo/orders is slower and fails 10%.
export const busyMetrics: MetricsResponse = {
  window: fifteenMinutes,
  summary: { ...stats(120, 3, 6, 81.25, 402.7), requests_per_minute: 8 },
  endpoints: [
    { method: 'POST', endpoint: '/demo/orders', ...stats(30, 3, 4, 180.4, 520.9) },
    { method: 'GET', endpoint: '/demo/users', ...stats(90, 0, 2, 48.2, 110.5) },
  ],
  status_codes: [
    { status_code: 200, count: 88 },
    { status_code: 201, count: 23 },
    { status_code: 404, count: 2 },
    { status_code: 422, count: 4 },
    { status_code: 503, count: 3 },
  ],
  latency_trend: {
    overall: buckets([
      stats(40, 0, 2, 70.1, 310.2),
      stats(40, 1, 2, 82.6, 398.4),
      stats(40, 2, 2, 91, 455.3),
    ]),
    by_endpoint: [
      {
        method: 'POST',
        endpoint: '/demo/orders',
        buckets: buckets([
          stats(10, 0, 1, 145.5, 410),
          stats(10, 1, 2, 180.7, 505.2),
          stats(10, 2, 1, 215, 560.4),
        ]),
      },
      {
        method: 'GET',
        endpoint: '/demo/users',
        buckets: buckets([
          stats(30, 0, 1, 45.3, 102.8),
          stats(30, 0, 0, 49.9, 112),
          stats(30, 0, 1, 49.4, 115.7),
        ]),
      },
    ],
  },
  recent_requests: [
    {
      id: 120,
      method: 'POST',
      endpoint: '/demo/orders',
      status_code: 503,
      latency_ms: 612.4,
      started_at: '2026-09-30T10:14:58.214Z',
    },
    {
      id: 119,
      method: 'GET',
      endpoint: '/demo/users',
      status_code: 200,
      latency_ms: 41.7,
      started_at: '2026-09-30T10:14:57.903Z',
    },
    {
      id: 118,
      method: 'GET',
      endpoint: '/demo/users',
      status_code: 404,
      latency_ms: 12.3,
      started_at: '2026-09-30T10:14:55.550Z',
    },
  ],
}

// The same window with no traffic: every bucket is still listed, so charts can show the gap.
export const emptyMetrics: MetricsResponse = {
  window: fifteenMinutes,
  summary: { ...stats(0, 0, 0), requests_per_minute: 0 },
  endpoints: [],
  status_codes: [],
  latency_trend: {
    overall: buckets([stats(0, 0, 0), stats(0, 0, 0), stats(0, 0, 0)]),
    by_endpoint: [],
  },
  recent_requests: [],
}
