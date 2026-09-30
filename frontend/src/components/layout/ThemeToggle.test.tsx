import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { THEME_STORAGE_KEY } from '../../hooks/useTheme'
import { ThemeToggle } from './ThemeToggle'

const root = document.documentElement

describe('ThemeToggle', () => {
  it('follows the system by default', () => {
    render(<ThemeToggle />)
    expect(screen.getByRole('radio', { name: 'System' })).toBeChecked()
    expect(root.dataset.theme).toBeUndefined()
  })

  it('applies and remembers a chosen theme, and forgets it for System', async () => {
    const user = userEvent.setup()
    render(<ThemeToggle />)

    await user.click(screen.getByRole('radio', { name: 'Dark' }))
    expect(root.dataset.theme).toBe('dark')
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')

    await user.click(screen.getByRole('radio', { name: 'System' }))
    expect(root.dataset.theme).toBeUndefined()
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBeNull()
  })

  it('starts from the saved theme', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'light')
    render(<ThemeToggle />)
    expect(screen.getByRole('radio', { name: 'Light' })).toBeChecked()
    expect(root.dataset.theme).toBe('light')
  })

  it('still works when storage is blocked', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError')
    })
    const user = userEvent.setup()
    render(<ThemeToggle />)
    await user.click(screen.getByRole('radio', { name: 'Dark' }))
    expect(root.dataset.theme).toBe('dark')
  })

  it('moves between options with the arrow keys', async () => {
    const user = userEvent.setup()
    render(<ThemeToggle />)
    await user.click(screen.getByRole('radio', { name: 'Light' }))
    await user.keyboard('{ArrowRight}')
    expect(screen.getByRole('radio', { name: 'Dark' })).toBeChecked()
  })
})
