import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { DEFAULT_WINDOW, findWindowPreset } from '../../models/windows'
import { RefreshControl } from './RefreshControl'
import { WindowSelector } from './WindowSelector'

describe('WindowSelector', () => {
  it('offers every preset and reports the chosen one', async () => {
    const onChange = vi.fn()
    render(<WindowSelector value={DEFAULT_WINDOW} onChange={onChange} />)
    const select = screen.getByRole('combobox', { name: 'Window' })
    expect(select).toHaveDisplayValue('1 hour')
    expect(screen.getAllByRole('option')).toHaveLength(5)

    await userEvent.selectOptions(select, '6 hours')
    expect(onChange).toHaveBeenCalledWith(findWindowPreset(360))
  })
})

describe('RefreshControl', () => {
  const props = {
    isFetching: false,
    autoRefresh: true,
    refreshSeconds: 15,
    onAutoRefreshChange: () => {},
    onRefresh: () => {},
  }

  it('says when nothing has loaded yet', () => {
    render(<RefreshControl {...props} updatedAt={0} />)
    expect(screen.getByText('Not loaded yet')).toBeInTheDocument()
  })

  it('counts up from the last update', () => {
    vi.useFakeTimers()
    try {
      render(<RefreshControl {...props} updatedAt={Date.now()} />)
      expect(screen.getByText('just now')).toBeInTheDocument()
      act(() => vi.advanceTimersByTime(12_000))
      expect(screen.getByText('12 s ago')).toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })

  it('toggles auto-refresh and refreshes on demand', async () => {
    const onAutoRefreshChange = vi.fn()
    const onRefresh = vi.fn()
    const user = userEvent.setup()
    render(
      <RefreshControl
        {...props}
        updatedAt={Date.now()}
        onAutoRefreshChange={onAutoRefreshChange}
        onRefresh={onRefresh}
      />,
    )
    await user.click(screen.getByRole('checkbox', { name: 'Auto-refresh every 15 s' }))
    expect(onAutoRefreshChange).toHaveBeenCalledWith(false)
    await user.click(screen.getByRole('button', { name: 'Refresh now' }))
    expect(onRefresh).toHaveBeenCalledOnce()
  })

  it('disables the button while a request is running', () => {
    render(<RefreshControl {...props} updatedAt={Date.now()} isFetching />)
    expect(screen.getByRole('button', { name: 'Refreshing…' })).toBeDisabled()
  })
})
