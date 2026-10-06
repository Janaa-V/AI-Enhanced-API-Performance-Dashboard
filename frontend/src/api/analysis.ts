import type { AnalysisRequest, AnalysisResponse } from '../models/analysis'
import { apiClient } from './client'

// Longer than the client's 10 s default: the backend gives the AI provider up to 30 s
// (AI_TIMEOUT_SECONDS) and then answers itself, so the browser should wait past that.
export const ANALYSIS_TIMEOUT_MS = 45_000

// POST /analyze. The server builds the model's input from its own aggregates; the client sends
// only the window. Resolves with "ok" or "no_data", or rejects with an ApiError.
export async function requestAnalysis(windowMinutes: number): Promise<AnalysisResponse> {
  // Typed against the contract, so a renamed field is a compile error here.
  const body: AnalysisRequest = { window_minutes: windowMinutes }
  const response = await apiClient.post<AnalysisResponse>('/analyze', body, {
    timeout: ANALYSIS_TIMEOUT_MS,
  })
  return response.data
}
