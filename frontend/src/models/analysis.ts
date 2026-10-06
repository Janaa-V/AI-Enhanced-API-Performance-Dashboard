// Readable names for the POST /analyze types, as models/metrics.ts does for GET /metrics.
// The answer is advice from a language model about the window's aggregates: observations quote
// the given numbers, hypotheses are at most "medium" confidence, and nothing claims a root cause.

import type { components } from '../api/schema.gen'

type Schemas = components['schemas']

export type AnalysisRequest = Schemas['AnalysisRequest']
// One shape for both outcomes: status "ok" with an analysis, or "no_data" (too little traffic,
// no provider called) with provider, model and analysis all null.
export type AnalysisResponse = Schemas['AnalysisResponse']
export type AnalysisWindow = Schemas['AnalysisWindow']
export type Analysis = Schemas['Analysis']
export type Observation = Schemas['Observation']
export type Hypothesis = Schemas['Hypothesis']

// The unions inside the schemas, taken from them rather than retyped, so a new metric or
// confidence level on the backend reaches the UI with the next `make api-types`.
export type Metric = Observation['metric']
export type Confidence = Hypothesis['confidence']
