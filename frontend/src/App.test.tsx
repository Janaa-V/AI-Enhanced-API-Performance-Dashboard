import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import App from './App'
import { busyMetrics } from './test/fixtures/metrics'
import { renderWithClient } from './test/render'
import { METRICS_URL, metricsHandlers, server } from './test/server'

describe('App', () => {
  it('renders the heading and the controls straight away', () => {
    renderWithClient(<App />)
    expect(screen.getByRole('heading', { name: 'API Performance Dashboard' })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Window' })).toBeInTheDocument()
    expect(screen.getAllByRole('status')[0]).toHaveTextContent('Loading')
  })

  it('shows the metrics once they load', async () => {
    renderWithClient(<App />)
    const kpis = await screen.findByRole('region', { name: 'Last 1 hour' })
    await waitFor(() => expect(within(kpis).getByText('120')).toBeInTheDocument())
    expect(screen.getByRole('region', { name: 'Latency over time' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Status codes' })).toHaveTextContent('2xx Success')
    expect(screen.getByText(/^Updated/)).toBeInTheDocument()
  })

  it('shows the empty state for a window without traffic', async () => {
    server.use(metricsHandlers.empty)
    renderWithClient(<App />)
    // Both charts and both tables say so; the KPI cards still show 0 requests and "—".
    expect(await screen.findAllByText('No requests in this window')).toHaveLength(4)
    const kpis = screen.getByRole('region', { name: 'Last 1 hour' })
    expect(within(kpis).getAllByText('—')).not.toHaveLength(0)
  })

  it('shows one error for the page when the first load fails, and recovers on retry', async () => {
    server.use(metricsHandlers.unavailable)
    const user = userEvent.setup()
    renderWithClient(<App />)
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('The service is temporarily unavailable.')
    expect(screen.queryByRole('region', { name: 'Last 1 hour' })).not.toBeInTheDocument()

    server.resetHandlers()
    await user.click(within(alert).getByRole('button', { name: 'Try again' }))
    expect(await screen.findByRole('region', { name: 'Last 1 hour' })).toBeInTheDocument()
  })

  it('keeps the last data when a refresh fails', async () => {
    const user = userEvent.setup()
    renderWithClient(<App />)
    const kpis = await screen.findByRole('region', { name: 'Last 1 hour' })
    await within(kpis).findByText('120')

    server.use(metricsHandlers.unavailable)
    await user.click(screen.getByRole('button', { name: 'Refresh now' }))
    expect(await screen.findByText(/The last refresh failed/)).toBeInTheDocument()
    expect(within(kpis).getByText('120')).toBeInTheDocument()
  })

  it('loads the chosen window and puts it in the URL', async () => {
    const windows: string[] = []
    server.use(
      http.get(METRICS_URL, ({ request }) => {
        windows.push(new URL(request.url).searchParams.get('window_minutes') ?? '')
        return HttpResponse.json(busyMetrics)
      }),
    )
    const user = userEvent.setup()
    renderWithClient(<App />)
    await screen.findByRole('region', { name: 'Last 1 hour' })

    await user.selectOptions(screen.getByRole('combobox', { name: 'Window' }), '6 hours')
    expect(await screen.findByRole('region', { name: 'Last 6 hours' })).toBeInTheDocument()
    expect(windows).toEqual(['60', '360'])
    expect(window.location.search).toBe('?window=360')
  })
})
