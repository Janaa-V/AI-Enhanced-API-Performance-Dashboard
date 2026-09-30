import { describe, expect, it } from 'vitest'
import type { LatencyTrend, TrendBucket } from '../models/metrics'
import { busyMetrics, emptyMetrics } from '../test/fixtures/metrics'
import { OVERALL_KEY, statusClass, toLatencyRows, toStatusClasses } from './chartData'

const t = (minute: number) => Date.UTC(2026, 8, 30, 10, minute)

function bucket(minute: number, p95: number | null, avg: number | null): TrendBucket {
  const empty = p95 === null
  return {
    start: new Date(t(minute)).toISOString(),
    end: new Date(t(minute + 5)).toISOString(),
    total_requests: empty ? 0 : 10,
    server_errors: 0,
    client_errors: 0,
    error_rate: empty ? null : 0,
    avg_latency_ms: avg,
    p95_latency_ms: p95,
  }
}

describe('toLatencyRows', () => {
  it('pivots the overall and per-endpoint trends into one row per bucket', () => {
    const { rows, seriesKeys } = toLatencyRows(busyMetrics.latency_trend, 'p95_latency_ms')
    expect(seriesKeys).toEqual(['POST /demo/orders', 'GET /demo/users'])
    expect(rows).toEqual([
      { time: t(0), [OVERALL_KEY]: 310.2, 'POST /demo/orders': 410, 'GET /demo/users': 102.8 },
      { time: t(5), [OVERALL_KEY]: 398.4, 'POST /demo/orders': 505.2, 'GET /demo/users': 112 },
      { time: t(10), [OVERALL_KEY]: 455.3, 'POST /demo/orders': 560.4, 'GET /demo/users': 115.7 },
    ])
  })

  it('reads the chosen metric', () => {
    const { rows } = toLatencyRows(busyMetrics.latency_trend, 'avg_latency_ms')
    expect(rows[0]).toMatchObject({ [OVERALL_KEY]: 70.1, 'GET /demo/users': 45.3 })
  })

  it('keeps null for an empty bucket, so the chart shows a gap rather than 0', () => {
    const trend: LatencyTrend = {
      overall: [bucket(0, 120, 60), bucket(5, 90, 40)],
      by_endpoint: [
        {
          method: 'GET',
          endpoint: '/demo/users',
          buckets: [bucket(0, 120, 60), bucket(5, 90, 40)],
        },
        {
          method: 'GET',
          endpoint: '/demo/search',
          buckets: [bucket(0, null, null), bucket(5, 80, 30)],
        },
      ],
    }
    const { rows } = toLatencyRows(trend, 'p95_latency_ms')
    expect(rows[0]).toEqual({
      time: t(0),
      [OVERALL_KEY]: 120,
      'GET /demo/users': 120,
      'GET /demo/search': null,
    })
  })

  it('sorts rows by time and gives every row every series key', () => {
    const trend: LatencyTrend = {
      overall: [bucket(5, 90, 40), bucket(0, 120, 60)],
      by_endpoint: [{ method: 'GET', endpoint: '/demo/users', buckets: [bucket(5, 90, 40)] }],
    }
    const { rows } = toLatencyRows(trend, 'p95_latency_ms')
    expect(rows.map((row) => row.time)).toEqual([t(0), t(5)])
    expect(rows[0]).toEqual({ time: t(0), [OVERALL_KEY]: 120, 'GET /demo/users': null })
  })

  it('returns empty buckets and no series for a window without traffic', () => {
    const { rows, seriesKeys } = toLatencyRows(emptyMetrics.latency_trend, 'p95_latency_ms')
    expect(seriesKeys).toEqual([])
    expect(rows).toHaveLength(3)
    expect(rows.every((row) => row[OVERALL_KEY] === null)).toBe(true)
  })
})

describe('statusClass', () => {
  it.each([
    [101, '1xx'],
    [200, '2xx'],
    [201, '2xx'],
    [304, '3xx'],
    [422, '4xx'],
    [599, '5xx'],
  ])('%i is %s', (code, expected) => {
    expect(statusClass(code)).toBe(expected)
  })
})

describe('toStatusClasses', () => {
  it('groups codes by class with their totals and a tone for colouring', () => {
    expect(toStatusClasses(busyMetrics.status_codes)).toEqual([
      {
        statusClass: '2xx',
        tone: 'success',
        count: 111,
        codes: [
          { status_code: 200, count: 88 },
          { status_code: 201, count: 23 },
        ],
      },
      {
        statusClass: '4xx',
        tone: 'warning',
        count: 6,
        codes: [
          { status_code: 404, count: 2 },
          { status_code: 422, count: 4 },
        ],
      },
      {
        statusClass: '5xx',
        tone: 'danger',
        count: 3,
        codes: [{ status_code: 503, count: 3 }],
      },
    ])
  })

  it('orders classes and codes even when the input is not sorted', () => {
    const groups = toStatusClasses([
      { status_code: 503, count: 1 },
      { status_code: 200, count: 5 },
      { status_code: 500, count: 2 },
    ])
    expect(groups.map((group) => group.statusClass)).toEqual(['2xx', '5xx'])
    expect(groups[1]?.codes.map((code) => code.status_code)).toEqual([500, 503])
  })

  it('returns nothing for a window without traffic', () => {
    expect(toStatusClasses(emptyMetrics.status_codes)).toEqual([])
  })
})
