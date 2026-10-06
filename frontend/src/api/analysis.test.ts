import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { noDataAnalysis, okAnalysis } from '../test/fixtures/analysis'
import { ANALYZE_URL, analysisHandlers, server } from '../test/server'
import { ANALYSIS_TIMEOUT_MS, requestAnalysis } from './analysis'
import { apiClient, REQUEST_TIMEOUT_MS } from './client'
import { ApiError } from './errors'

async function analysisError(): Promise<ApiError> {
  const error: unknown = await requestAnalysis(15).catch((caught: unknown) => caught)
  expect(error).toBeInstanceOf(ApiError)
  return error as ApiError
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('requestAnalysis', () => {
  it('posts the window in snake_case and returns the answer', async () => {
    const bodies: unknown[] = []
    server.use(
      http.post(ANALYZE_URL, async ({ request }) => {
        bodies.push(await request.json())
        return HttpResponse.json(okAnalysis)
      }),
    )
    await expect(requestAnalysis(15)).resolves.toEqual(okAnalysis)
    expect(bodies).toEqual([{ window_minutes: 15 }])
  })

  it('returns a no_data answer as a success, not an error', async () => {
    server.use(analysisHandlers.noData)
    await expect(requestAnalysis(15)).resolves.toEqual(noDataAnalysis)
  })

  it('waits longer than other requests, past the backend provider timeout', async () => {
    const post = vi.spyOn(apiClient, 'post')
    await requestAnalysis(15)
    expect(post).toHaveBeenCalledWith('/analyze', expect.anything(), {
      timeout: ANALYSIS_TIMEOUT_MS,
    })
    // The backend's AI_TIMEOUT_SECONDS defaults to 30.
    expect(ANALYSIS_TIMEOUT_MS).toBeGreaterThan(30_000)
    expect(ANALYSIS_TIMEOUT_MS).toBeGreaterThan(REQUEST_TIMEOUT_MS)
  })

  it('rejects with ai_disabled when the server has no provider', async () => {
    server.use(analysisHandlers.disabled)
    expect(await analysisError()).toMatchObject({
      kind: 'server',
      status: 503,
      code: 'ai_disabled',
      message: 'AI analysis is not configured on this server.',
    })
  })

  it('rejects with rate_limited and the wait from Retry-After', async () => {
    server.use(analysisHandlers.rateLimited)
    expect(await analysisError()).toMatchObject({
      kind: 'rate_limited',
      status: 429,
      code: 'rate_limited',
      retryAfterSeconds: 30,
    })
  })

  it('rejects with ai_unavailable when the provider fails', async () => {
    server.use(analysisHandlers.unavailable)
    expect(await analysisError()).toMatchObject({
      kind: 'server',
      status: 502,
      code: 'ai_unavailable',
    })
  })

  it('rejects with a network error when the backend cannot be reached', async () => {
    server.use(analysisHandlers.networkError)
    expect(await analysisError()).toMatchObject({ kind: 'network', status: undefined })
  })
})
