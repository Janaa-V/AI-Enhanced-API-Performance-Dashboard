import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'
import { okAnalysis } from '../test/fixtures/analysis'
import { renderHookWithClient } from '../test/render'
import { ANALYZE_URL, server } from '../test/server'
import { useAnalysis } from './useAnalysis'

// Answers with the given status code (the success fixture for 200), counting calls.
function countCalls(status = 200) {
  let calls = 0
  server.use(
    http.post(ANALYZE_URL, () => {
      calls += 1
      return status === 200
        ? HttpResponse.json(okAnalysis)
        : HttpResponse.json(
            { error: { code: 'ai_unavailable', message: 'Provider failed.' } },
            { status },
          )
    }),
  )
  return () => calls
}

describe('useAnalysis', () => {
  it('does nothing until asked', async () => {
    const calls = countCalls()
    const { result } = renderHookWithClient(() => useAnalysis())
    expect(result.current.isIdle).toBe(true)
    // Give a query-style hook time to fire on its own; a mutation never does.
    await new Promise((resolve) => setTimeout(resolve, 20))
    expect(calls()).toBe(0)
  })

  it('posts the window when asked and keeps the answer', async () => {
    const calls = countCalls()
    const { result } = renderHookWithClient(() => useAnalysis())
    act(() => result.current.mutate(15))
    await waitFor(() => expect(result.current.data).toEqual(okAnalysis))
    expect(calls()).toBe(1)
  })

  it('never retries a failure on its own, whatever the client default', async () => {
    const calls = countCalls(502)
    // A client that would retry every mutation three times, at once: the hook must override it.
    const client = new QueryClient({ defaultOptions: { mutations: { retry: 3, retryDelay: 0 } } })
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    )
    const { result } = renderHook(() => useAnalysis(), { wrapper })
    act(() => result.current.mutate(15))
    await waitFor(() => expect(result.current.error?.code).toBe('ai_unavailable'))
    await new Promise((resolve) => setTimeout(resolve, 20))
    expect(calls()).toBe(1)
  })
})
