import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { EndpointMetrics, RecentRequest } from '../../models/metrics'
import { busyMetrics } from '../../test/fixtures/metrics'
import { EndpointTable } from './EndpointTable'
import { RecentRequestsTable } from './RecentRequestsTable'

// The row headers (first cells) in display order.
function firstColumn(): string[] {
  return within(screen.getByRole('table'))
    .getAllByRole('row')
    .slice(1)
    .map((row) => row.firstElementChild?.textContent ?? '')
}

function header(name: string) {
  return screen.getByRole('columnheader', { name: new RegExp(`^${name}`) })
}

describe('EndpointTable', () => {
  const idle: EndpointMetrics = {
    method: 'GET',
    endpoint: '/demo/reports',
    total_requests: 0,
    server_errors: 0,
    client_errors: 0,
    error_rate: null,
    avg_latency_ms: null,
    p95_latency_ms: null,
  }
  const endpoints = [...busyMetrics.endpoints, idle]

  it('starts slowest first, with an endpoint that has no latency last', () => {
    render(<EndpointTable endpoints={endpoints} />)
    expect(firstColumn()).toEqual(['POST/demo/orders', 'GET/demo/users', 'GET/demo/reports'])
    expect(header('p95')).toHaveAttribute('aria-sort', 'descending')
    expect(header('Requests')).toHaveAttribute('aria-sort', 'none')
  })

  it('sorts by another column and flips on a second click, keeping null last', async () => {
    const user = userEvent.setup()
    render(<EndpointTable endpoints={endpoints} />)

    await user.click(within(header('Average')).getByRole('button'))
    expect(header('Average')).toHaveAttribute('aria-sort', 'descending')
    expect(firstColumn()).toEqual(['POST/demo/orders', 'GET/demo/users', 'GET/demo/reports'])

    await user.click(within(header('Average')).getByRole('button'))
    expect(header('Average')).toHaveAttribute('aria-sort', 'ascending')
    expect(firstColumn()).toEqual(['GET/demo/users', 'POST/demo/orders', 'GET/demo/reports'])
  })

  it('sorts text columns A to Z first', async () => {
    render(<EndpointTable endpoints={endpoints} />)
    await userEvent.click(within(header('Endpoint')).getByRole('button'))
    expect(firstColumn()).toEqual(['GET/demo/reports', 'GET/demo/users', 'POST/demo/orders'])
  })

  it('shows "—" for what an idle endpoint cannot measure', () => {
    render(<EndpointTable endpoints={[idle]} />)
    const cells = within(screen.getAllByRole('row')[1]!).getAllByRole('cell')
    expect(cells.map((cell) => cell.textContent)).toEqual(['0', '—', '0', '0', '—', '—'])
  })
})

describe('RecentRequestsTable', () => {
  // Fractional and whole seconds mixed: as text, "…:58.214Z" would sort before "…:58Z".
  const requests: RecentRequest[] = [
    { ...busyMetrics.recent_requests[0]!, id: 3, started_at: '2026-09-30T10:14:58.214Z' },
    { ...busyMetrics.recent_requests[1]!, id: 2, started_at: '2026-09-30T10:14:58Z' },
    { ...busyMetrics.recent_requests[2]!, id: 1, started_at: '2026-09-30T10:14:57.500Z' },
  ]

  it('shows the newest first, in local time, with error statuses marked', () => {
    render(<RecentRequestsTable requests={requests} />)
    expect(firstColumn()).toEqual(['15:44:58', '15:44:58', '15:44:57'])
    const rows = screen.getAllByRole('row')
    expect(rows[1]).toHaveTextContent('✕ 503')
    expect(rows[3]).toHaveTextContent('! 404')
  })

  it('sorts times as instants, not as text', async () => {
    const user = userEvent.setup()
    render(<RecentRequestsTable requests={requests} />)
    await user.click(within(header('Time')).getByRole('button'))
    expect(header('Time')).toHaveAttribute('aria-sort', 'ascending')
    const ids = screen
      .getAllByRole('row')
      .slice(1)
      .map((row) => within(row).getAllByRole('cell')[3]?.textContent)
    expect(ids).toEqual(['! 404', '200', '✕ 503'])
  })

  it('sorts by latency, slowest first', async () => {
    render(<RecentRequestsTable requests={requests} />)
    await userEvent.click(within(header('Latency')).getByRole('button'))
    const latencies = screen
      .getAllByRole('row')
      .slice(1)
      .map((row) => within(row).getAllByRole('cell')[4]?.textContent)
    expect(latencies).toEqual(['612 ms', '42 ms', '12 ms'])
  })
})
