import { useMutation } from '@tanstack/react-query'
import { requestAnalysis } from '../api/analysis'

// POST /analyze as a mutation, not a query: it runs only when the user asks, never on mount,
// focus or an interval, because every call may spend the server's AI quota.
// Call `mutate(windowMinutes)`; the state (pending, error, data) belongs to this component only.
export function useAnalysis() {
  return useMutation({
    mutationKey: ['analysis'],
    mutationFn: (windowMinutes: number) => requestAnalysis(windowMinutes),
    // Never retried automatically, unlike the metrics query: a retry would spend quota again,
    // and a 429 or ai_disabled would fail the same way. The panel offers a button instead.
    retry: false,
  })
}
