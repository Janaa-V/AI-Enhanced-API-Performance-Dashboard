import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { API_URL } from '../../config'
import { cachedAnalysis, okAnalysis } from '../../test/fixtures/analysis'
import { renderWithClient } from '../../test/render'
import { ANALYZE_URL, analysisHandlers, server } from '../../test/server'
import { AnalysisResult } from './AnalysisResult'
import { InsightsPanel } from './InsightsPanel'

function renderPanel() {
  // Only the rate-limit test fakes the clock; user-event must move it then.
  const user = userEvent.setup({
    advanceTimers: (ms) => {
      if (vi.isFakeTimers()) vi.advanceTimersByTime(ms)
    },
  })
  renderWithClient(<InsightsPanel windowMinutes={15} windowLabel="15 min" />)
  const panel = screen.getByRole('region', { name: 'AI insights' })
  const start = () =>
    user.click(within(panel).getByRole('button', { name: 'Analyse the last 15 min' }))
  return { user, panel, start }
}

afterEach(() => {
  vi.useRealTimers()
})

describe('InsightsPanel', () => {
  it('sends nothing until asked, and says what the analysis sees', async () => {
    const calls: unknown[] = []
    server.use(
      http.post(ANALYZE_URL, async ({ request }) => {
        calls.push(await request.json())
        return HttpResponse.json(okAnalysis)
      }),
    )
    const { panel, start } = renderPanel()
    expect(panel).toHaveTextContent('aggregate numbers, never individual requests')
    expect(calls).toEqual([])

    await start()
    expect(await within(panel).findByText(okAnalysis.analysis!.headline)).toBeInTheDocument()
    expect(calls).toEqual([{ window_minutes: 15 }])
  })

  it('says it is working while the answer is on its way', async () => {
    server.use(
      http.post(ANALYZE_URL, async () => {
        await delay(50)
        return HttpResponse.json(okAnalysis)
      }),
    )
    const { panel, start } = renderPanel()
    await start()
    expect(within(panel).getByRole('status')).toHaveTextContent('Analysing the last 15 min')
    expect(within(panel).queryByRole('button')).not.toBeInTheDocument()
    await within(panel).findByText(okAnalysis.analysis!.headline)
  })

  it('runs again on request and labels a cached answer', async () => {
    const { user, panel, start } = renderPanel()
    await start()
    await within(panel).findByText(okAnalysis.analysis!.headline)
    expect(panel).not.toHaveTextContent('(cached)')

    server.use(http.post(ANALYZE_URL, () => HttpResponse.json(cachedAnalysis)))
    await user.click(within(panel).getByRole('button', { name: 'Analyse again' }))
    expect(await within(panel).findByText(/\(cached\)/)).toBeInTheDocument()
  })

  it('explains a window with too little traffic, without calling it an error', async () => {
    server.use(analysisHandlers.noData)
    const { panel, start } = renderPanel()
    await start()
    expect(await within(panel).findByText('Too little traffic to analyse')).toBeInTheDocument()
    expect(within(panel).getByText('make traffic')).toBeInTheDocument()
    expect(within(panel).queryByRole('alert')).not.toBeInTheDocument()
    expect(within(panel).getByRole('button', { name: 'Analyse again' })).toBeInTheDocument()
  })

  it('says how to turn AI on when it is off, with no retry that cannot help', async () => {
    server.use(analysisHandlers.disabled)
    const { panel, start } = renderPanel()
    await start()
    const alert = await within(panel).findByRole('alert')
    expect(alert).toHaveTextContent('AI analysis is turned off')
    expect(alert).toHaveTextContent('AI_PROVIDER')
    expect(within(panel).queryByRole('button')).not.toBeInTheDocument()
  })

  it('makes the user wait out a rate limit before retrying', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    server.use(analysisHandlers.rateLimited)
    const { user, panel, start } = renderPanel()
    await start()

    const alert = await within(panel).findByRole('alert')
    expect(alert).toHaveTextContent('Analysis limit reached')
    expect(within(alert).getByRole('button', { name: 'Try again in 30 s' })).toBeDisabled()

    // Exactly at the boundary: one second left at 29 s, enabled at 30 s.
    await act(() => vi.advanceTimersByTimeAsync(29_000))
    expect(within(alert).getByRole('button', { name: 'Try again in 1 s' })).toBeDisabled()

    await act(() => vi.advanceTimersByTimeAsync(1_000))
    server.use(analysisHandlers.success)
    await user.click(within(alert).getByRole('button', { name: 'Try again' }))
    expect(await within(panel).findByText(okAnalysis.analysis!.headline)).toBeInTheDocument()
  })

  it('lets the user retry at once when a rate limit gives no wait', async () => {
    server.use(
      http.post(ANALYZE_URL, () =>
        HttpResponse.json({ error: { code: 'rate_limited', message: 'Busy.' } }, { status: 429 }),
      ),
    )
    const { panel, start } = renderPanel()
    await start()
    const alert = await within(panel).findByRole('alert')
    expect(within(alert).getByRole('button', { name: 'Try again' })).toBeEnabled()
  })

  it('offers a retry when the provider fails, and recovers', async () => {
    server.use(analysisHandlers.unavailable)
    const { user, panel, start } = renderPanel()
    await start()
    const alert = await within(panel).findByRole('alert')
    expect(alert).toHaveTextContent('The AI provider did not answer')
    expect(alert).toHaveTextContent('could not produce an analysis')

    server.use(analysisHandlers.success)
    await user.click(within(alert).getByRole('button', { name: 'Try again' }))
    expect(await within(panel).findByText(okAnalysis.analysis!.headline)).toBeInTheDocument()
  })

  it('names the API URL when the backend cannot be reached', async () => {
    server.use(analysisHandlers.networkError)
    const { panel, start } = renderPanel()
    await start()
    const alert = await within(panel).findByRole('alert')
    expect(alert).toHaveTextContent('The analysis failed')
    expect(alert).toHaveTextContent(API_URL)
    expect(within(alert).getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })
})

describe('AnalysisResult', () => {
  const analysis = okAnalysis.analysis!

  it('keeps observations, hypotheses and next steps in their own labelled sections', () => {
    render(<AnalysisResult analysis={analysis} response={okAnalysis} />)
    const observations = screen.getByRole('region', { name: 'Observations' })
    expect(within(observations).getAllByRole('listitem')).toHaveLength(3)
    expect(observations).toHaveTextContent('POST /demo/orders · p95 latency')
    expect(observations).toHaveTextContent('All endpoints · Requests per minute')

    const causes = screen.getByRole('region', { name: 'Possible causes' })
    expect(causes).toHaveTextContent('Ideas to check, not findings.')
    expect(causes).toHaveTextContent('Medium confidence')
    expect(causes).toHaveTextContent('Low confidence')

    const steps = screen.getByRole('region', { name: 'What to check next' })
    expect(within(steps).getAllByRole('listitem')).toHaveLength(2)
  })

  it('labels the answer as AI-assisted, with its source and the window it covers', () => {
    render(<AnalysisResult analysis={analysis} response={okAnalysis} />)
    // Tests run in Asia/Kolkata: 10:00 UTC is 15:30 local.
    // A <footer> inside a section has no landmark role in browsers, so it is found by its text.
    expect(screen.getByText('AI-assisted analysis').parentElement).toHaveTextContent(
      'AI-assisted analysis of 15:30–15:45 by groq (openai/gpt-oss-120b), generated at 15:45:02.',
    )
  })

  it('names a provider whose model has the same name only once', () => {
    render(
      <AnalysisResult
        analysis={analysis}
        response={{ ...okAnalysis, provider: 'fake', model: 'fake' }}
      />,
    )
    expect(screen.getByText('AI-assisted analysis').parentElement).toHaveTextContent(
      'AI-assisted analysis of 15:30–15:45 by fake, generated at 15:45:02.',
    )
  })

  it('leaves out empty sections', () => {
    render(
      <AnalysisResult
        analysis={{ ...analysis, hypotheses: [], next_steps: [] }}
        response={okAnalysis}
      />,
    )
    expect(screen.getByRole('region', { name: 'Observations' })).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Possible causes' })).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'What to check next' })).not.toBeInTheDocument()
  })
})
