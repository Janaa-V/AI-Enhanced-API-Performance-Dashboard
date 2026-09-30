import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { busyMetrics, emptyMetrics } from '../../test/fixtures/metrics'
import { KpiGrid } from './KpiGrid'

// Each card is a term (the label) and its description (the value).
function valueOf(label: string): string | null | undefined {
  return screen.getByText(label, { selector: 'dt' }).nextElementSibling?.textContent
}

describe('KpiGrid', () => {
  it('shows the headline numbers, formatted', () => {
    render(<KpiGrid summary={busyMetrics.summary} />)
    expect(valueOf('Requests')).toBe('120')
    expect(valueOf('Requests per minute')).toBe('8.0 req/min')
    expect(valueOf('Error rate')).toBe('2.5 %')
    expect(valueOf('Average latency')).toBe('81 ms')
    expect(valueOf('p95 latency')).toBe('403 ms')
    // 4xx are not errors, but they are shown beside the rate.
    expect(screen.getByText(/3 server \(5xx\) · 6 client \(4xx\)/)).toBeInTheDocument()
  })

  it('shows 0 for counts and "—" for what an empty window cannot measure', () => {
    render(<KpiGrid summary={emptyMetrics.summary} />)
    expect(valueOf('Requests')).toBe('0')
    expect(valueOf('Error rate')).toBe('—')
    expect(valueOf('Average latency')).toBe('—')
    expect(valueOf('p95 latency')).toBe('—')
  })
})
