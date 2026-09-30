// Reshapes the /metrics response into the rows and groups the charts draw. Values stay raw; the
// charts format them with lib/format.ts.
import type { LatencyTrend, StatusCodeCount } from '../models/metrics'
import { endpointKey } from './endpoints'

export type LatencyMetric = 'p95_latency_ms' | 'avg_latency_ms'

// The series key for the all-endpoints line. Endpoint keys contain a space, so they never clash.
export const OVERALL_KEY = 'overall'

// One row per bucket: its start in epoch milliseconds, then one value per series. null means the
// bucket had no requests, so the chart draws a gap there instead of a false drop to 0.
export interface LatencyRow {
  time: number
  [series: string]: number | null
}

export interface LatencyChartData {
  rows: LatencyRow[]
  // Endpoint series in the backend's order (by route, then method), without OVERALL_KEY.
  seriesKeys: string[]
}

// Pivots the trend into rows. Every row has every series key, which Recharts needs: it reads a
// key that is present as-is, but would parse a missing one as a property path.
export function toLatencyRows(trend: LatencyTrend, metric: LatencyMetric): LatencyChartData {
  const rows = new Map<number, LatencyRow>()
  const rowAt = (start: string): LatencyRow => {
    const time = Date.parse(start)
    let row = rows.get(time)
    if (!row) {
      row = { time, [OVERALL_KEY]: null }
      rows.set(time, row)
    }
    return row
  }

  for (const bucket of trend.overall) {
    rowAt(bucket.start)[OVERALL_KEY] = bucket[metric]
  }
  const seriesKeys = trend.by_endpoint.map((series) => {
    const key = endpointKey(series)
    for (const bucket of series.buckets) {
      rowAt(bucket.start)[key] = bucket[metric]
    }
    return key
  })

  // The backend lists every bucket for every series; this only guards against a gap.
  const sorted = [...rows.values()].sort((a, b) => a.time - b.time)
  for (const row of sorted) {
    for (const key of seriesKeys) row[key] ??= null
  }
  return { rows: sorted, seriesKeys }
}

export type StatusClass = '1xx' | '2xx' | '3xx' | '4xx' | '5xx'

// Which status token colours the class: 2xx success, 4xx warning, 5xx danger.
export type StatusTone = 'neutral' | 'success' | 'warning' | 'danger'

export interface StatusClassGroup {
  statusClass: StatusClass
  tone: StatusTone
  count: number
  // The codes inside the class, ascending, for the tooltip: 503 x 3, 504 x 1.
  codes: StatusCodeCount[]
}

const TONES: Record<StatusClass, StatusTone> = {
  '1xx': 'neutral',
  '2xx': 'success',
  '3xx': 'neutral',
  '4xx': 'warning',
  '5xx': 'danger',
}

export function statusClass(statusCode: number): StatusClass {
  return `${Math.floor(statusCode / 100)}xx` as StatusClass
}

// Groups status codes by class, ascending. Only classes that occurred are listed, matching the
// backend, which lists only codes that occurred.
export function toStatusClasses(codes: StatusCodeCount[]): StatusClassGroup[] {
  const groups = new Map<StatusClass, StatusClassGroup>()
  for (const code of [...codes].sort((a, b) => a.status_code - b.status_code)) {
    const cls = statusClass(code.status_code)
    let group = groups.get(cls)
    if (!group) {
      group = { statusClass: cls, tone: TONES[cls], count: 0, codes: [] }
      groups.set(cls, group)
    }
    group.count += code.count
    group.codes.push(code)
  }
  return [...groups.values()]
}
