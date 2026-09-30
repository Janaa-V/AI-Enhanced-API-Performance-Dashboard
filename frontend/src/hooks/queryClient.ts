import { QueryClient } from '@tanstack/react-query'
import { ApiError } from '../api/errors'

// Every query function rejects with an ApiError (api/client.ts), so query errors are typed as one.
declare module '@tanstack/react-query' {
  interface Register {
    defaultError: ApiError
  }
}

const MAX_RETRIES = 2

// Retry what may pass on a second try: an unreachable backend, a timeout, a 5xx. Never retry a
// 4xx: the same request would fail the same way.
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (failureCount >= MAX_RETRIES) return false
  if (!(error instanceof ApiError)) return false
  return error.kind === 'network' || error.kind === 'timeout' || error.kind === 'server'
}

// One place for the defaults, so tests build the same client (with retries off).
export function createQueryClient({ retry = true }: { retry?: boolean } = {}): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // A snapshot this recent is shown as is, without refetching, when a component remounts.
        staleTime: 10_000,
        retry: retry ? shouldRetry : false,
      },
    },
  })
}
