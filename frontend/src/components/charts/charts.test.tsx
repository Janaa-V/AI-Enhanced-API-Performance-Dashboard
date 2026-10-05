import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { busyMetrics } from '../../test/fixtures/metrics'
import { LatencyChart } from './LatencyChart'
import { LatencyPanel } from './LatencyPanel'
import { StatusCodeChart } from './StatusCodeChart'

// jsdom has no layout, so these check what does not depend on it: the legend, the summaries
// and the table view. The drawn chart is checked in a real browser.

describe('LatencyChart', () => {
  const chart = (
    <LatencyChart
      trend={busyMetrics.latency_trend}
      metric="p95_latency_ms"
      range={busyMetrics.window}
    />
  )

  it('names every series in the legend, all endpoints last', () => {
    render(chart)
    const items = within(screen.getByRole('list')).getAllByRole('listitem')
    expect(items.map((item) => item.textContent)).toEqual([
      'POST /demo/orders',
      'GET /demo/users',
      'All endpoints',
    ])
  })

  it('summarises the chart for screen readers', () => {
    render(chart)
    // Times are shown in the test zone, Asia/Kolkata (UTC+05:30).
    expect(
      screen.getByText(
        'p95 latency for all endpoints between 15:30 to 15:45, highest 455 ms at 15:40.',
      ),
    ).toBeInTheDocument()
  })

  it('has every value in its table view', async () => {
    render(chart)
    await userEvent.click(screen.getByText('Show as table'))
    const table = screen.getByRole('table', { name: 'p95 latency per 5-minute bucket' })
    const rows = within(table).getAllByRole('row')
    expect(rows).toHaveLength(4)
    expect(
      within(rows[1]!)
        .getAllByRole('cell')
        .map((cell) => cell.textContent),
    ).toEqual(['410 ms', '103 ms', '310 ms'])
  })
})

describe('LatencyPanel', () => {
  it('switches between p95 and average', async () => {
    const user = userEvent.setup()
    render(<LatencyPanel status="ready" data={busyMetrics} />)
    expect(screen.getByRole('radio', { name: 'p95' })).toBeChecked()
    await user.click(screen.getByRole('radio', { name: 'Average' }))
    expect(screen.getByText(/^Average latency for all endpoints/)).toBeInTheDocument()
  })
})

describe('StatusCodeChart', () => {
  it('states each class total as text, with a symbol, not only a colour', () => {
    render(<StatusCodeChart codes={busyMetrics.status_codes} />)
    const classes = within(screen.getByRole('list')).getAllByRole('listitem')
    expect(classes.map((item) => item.textContent)).toEqual([
      '✓2xx Success: 111 (92.5 %)',
      '!4xx Client error: 6 (5.0 %)',
      '✕5xx Server error: 3 (2.5 %)',
    ])
  })

  it('lists every code in its table view', async () => {
    render(<StatusCodeChart codes={busyMetrics.status_codes} />)
    await userEvent.click(screen.getByText('Show as table'))
    const table = screen.getByRole('table', { name: 'Responses by status code' })
    expect(within(table).getAllByRole('row')).toHaveLength(6)
    expect(within(table).getByRole('rowheader', { name: '503' }).parentElement).toHaveTextContent(
      '503Server error32.5 %',
    )
  })
})
