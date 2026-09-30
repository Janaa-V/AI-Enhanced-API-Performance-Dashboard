import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { API_URL } from '../../config'
import { ErrorState } from './ErrorState'
import { Panel } from './Panel'

describe('Panel', () => {
  it('names its section after the title and shows the content when ready', () => {
    render(
      <Panel title="Latency" status="ready" actions={<button type="button">p95</button>}>
        <p>chart</p>
      </Panel>,
    )
    expect(screen.getByRole('region', { name: 'Latency' })).toHaveTextContent('chart')
    expect(screen.getByRole('button', { name: 'p95' })).toBeInTheDocument()
  })

  it('shows a loading status instead of the content or its actions', () => {
    render(
      <Panel title="Latency" status="loading" actions={<button type="button">p95</button>}>
        <p>chart</p>
      </Panel>,
    )
    expect(screen.getByRole('status')).toHaveTextContent('Loading')
    expect(screen.queryByText('chart')).not.toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('shows how to create traffic when empty, or a custom message', () => {
    const { rerender } = render(
      <Panel title="Latency" status="empty">
        <p>chart</p>
      </Panel>,
    )
    expect(screen.getByText('make traffic')).toBeInTheDocument()
    rerender(
      <Panel title="Latency" status="empty" emptyMessage="No endpoints yet.">
        <p>chart</p>
      </Panel>,
    )
    expect(screen.getByText('No endpoints yet.')).toBeInTheDocument()
  })

  it('shows the error with a retry button', async () => {
    const onRetry = vi.fn()
    render(
      <Panel
        title="Latency"
        status="error"
        error={{ kind: 'server', message: 'The service is temporarily unavailable.' }}
        onRetry={onRetry}
      >
        <p>chart</p>
      </Panel>,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('The service is temporarily unavailable.')
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(onRetry).toHaveBeenCalledOnce()
  })
})

describe('ErrorState', () => {
  it('names the configured API URL when the backend cannot be reached', () => {
    render(<ErrorState error={{ kind: 'network', message: 'Could not reach the API.' }} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Cannot reach the API')
    expect(screen.getByText(API_URL)).toBeInTheDocument()
  })

  it('does not mention the URL for a server error', () => {
    render(<ErrorState error={{ kind: 'server', message: 'Down.' }} />)
    expect(screen.queryByText(API_URL)).not.toBeInTheDocument()
  })
})
