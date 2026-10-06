// Typed POST /analyze responses for tests, shaped like the backend's: the observations quote
// numbers from busyMetrics (fixtures/metrics.ts) and name only its endpoints.
import type { AnalysisResponse } from '../../models/analysis'

const window = {
  start: '2026-09-30T10:00:00Z',
  end: '2026-09-30T10:15:00Z',
  window_minutes: 15,
}

export const okAnalysis: AnalysisResponse = {
  status: 'ok',
  window,
  generated_at: '2026-09-30T10:15:02Z',
  provider: 'groq',
  model: 'openai/gpt-oss-120b',
  cached: false,
  analysis: {
    headline: 'POST /demo/orders is the slowest endpoint and the only one with server errors.',
    observations: [
      {
        endpoint: 'POST /demo/orders',
        metric: 'p95_latency_ms',
        text: 'p95 latency is 520.9 ms, against 110.5 ms for GET /demo/users.',
      },
      {
        endpoint: 'POST /demo/orders',
        metric: 'error_rate',
        text: '3 of 30 requests (10%) ended in a server error.',
      },
      {
        endpoint: null,
        metric: 'requests_per_minute',
        text: 'Traffic averaged 8 requests per minute across the API.',
      },
    ],
    hypotheses: [
      {
        text: 'Order creation may depend on a slower downstream step than the reads.',
        confidence: 'medium',
      },
      { text: 'The errors may come in bursts rather than evenly.', confidence: 'low' },
    ],
    next_steps: [
      'Compare the error times of POST /demo/orders with its latency trend.',
      'Check whether the slow orders share a time of day.',
    ],
  },
}

// The same answer served from the backend's 60-second cache.
export const cachedAnalysis: AnalysisResponse = { ...okAnalysis, cached: true }

// Too little traffic: the backend answers without calling a provider.
export const noDataAnalysis: AnalysisResponse = {
  status: 'no_data',
  window,
  generated_at: '2026-09-30T10:15:02Z',
  provider: null,
  model: null,
  cached: false,
  analysis: null,
}
