import { isCancel } from 'axios'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { busyMetrics, emptyMetrics } from '../test/fixtures/metrics'
import { METRICS_URL, metricsHandlers, server } from '../test/server'
import { ApiError } from './errors'
import { fetchMetrics } from './metrics'

const params = { windowMinutes: 15, bucketMinutes: 5 }

// Serves busyMetrics and records the query string the client sent.
function captureQuery(): URLSearchParams {
  const query = new URLSearchParams()
  server.use(
    http.get(METRICS_URL, ({ request }) => {
      new URL(request.url).searchParams.forEach((value, key) => query.append(key, value))
      return HttpResponse.json(busyMetrics)
    }),
  )
  return query
}

async function fetchError(): Promise<ApiError> {
  const error: unknown = await fetchMetrics(params).catch((caught: unknown) => caught)
  expect(error).toBeInstanceOf(ApiError)
  return error as ApiError
}

describe('fetchMetrics', () => {
  it('sends the parameters in snake_case and returns the response', async () => {
    const query = captureQuery()
    await expect(fetchMetrics({ ...params, recentLimit: 10 })).resolves.toEqual(busyMetrics)
    expect(Object.fromEntries(query)).toEqual({
      window_minutes: '15',
      bucket_minutes: '5',
      recent_limit: '10',
    })
  })

  it('leaves recent_limit to the backend when it is not given', async () => {
    const query = captureQuery()
    await fetchMetrics(params)
    expect(query.has('recent_limit')).toBe(false)
  })

  it('keeps nulls for a window with no requests', async () => {
    server.use(metricsHandlers.empty)
    const metrics = await fetchMetrics(params)
    expect(metrics.summary).toMatchObject({ total_requests: 0, error_rate: null })
    expect(metrics.latency_trend.overall).toHaveLength(3)
  })

  it('rejects with the server message when the backend is unavailable', async () => {
    server.use(metricsHandlers.unavailable)
    expect(await fetchError()).toMatchObject({
      kind: 'server',
      status: 503,
      code: 'service_unavailable',
      message: 'The service is temporarily unavailable.',
    })
  })

  it('rejects with the validation hint for bad parameters', async () => {
    server.use(metricsHandlers.validationError)
    const error = await fetchError()
    expect(error).toMatchObject({ kind: 'validation', status: 422 })
    expect(error.message).toMatch(/^Too many buckets/)
  })

  it('rejects with a network error when the backend cannot be reached', async () => {
    server.use(metricsHandlers.networkError)
    expect(await fetchError()).toMatchObject({ kind: 'network', status: undefined })
  })

  it('passes cancellation through instead of turning it into an ApiError', async () => {
    const controller = new AbortController()
    controller.abort()
    const error: unknown = await fetchMetrics(params, controller.signal).catch((caught) => caught)
    expect(isCancel(error)).toBe(true)
    expect(error).not.toBeInstanceOf(ApiError)
  })
})

describe('fixtures', () => {
  it('add up like a real response', () => {
    const { summary, endpoints, status_codes, latency_trend } = busyMetrics
    const sum = (values: number[]) => values.reduce((total, value) => total + value, 0)
    expect(sum(endpoints.map((e) => e.total_requests))).toBe(summary.total_requests)
    expect(sum(endpoints.map((e) => e.server_errors))).toBe(summary.server_errors)
    expect(sum(endpoints.map((e) => e.client_errors))).toBe(summary.client_errors)
    expect(sum(status_codes.map((s) => s.count))).toBe(summary.total_requests)
    expect(sum(latency_trend.overall.map((b) => b.total_requests))).toBe(summary.total_requests)
    expect(emptyMetrics.summary.avg_latency_ms).toBeNull()
  })
})
