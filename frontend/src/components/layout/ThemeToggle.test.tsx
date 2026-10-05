import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import indexHtml from '../../../index.html?raw'
import { THEME_STORAGE_KEY } from '../../hooks/useTheme'
import { ThemeToggle } from './ThemeToggle'

const root = document.documentElement

function blockStorage() {
  const blocked = () => {
    throw new DOMException('blocked', 'SecurityError')
  }
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(blocked)
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(blocked)
}

describe('ThemeToggle', () => {
  it('starts dark by default', () => {
    render(<ThemeToggle />)
    expect(screen.getByRole('radio', { name: 'Dark' })).toBeChecked()
    expect(root.dataset.theme).toBe('dark')
  })

  it('applies and remembers each choice, System included', async () => {
    const user = userEvent.setup()
    render(<ThemeToggle />)

    await user.click(screen.getByRole('radio', { name: 'Light' }))
    expect(root.dataset.theme).toBe('light')
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('light')

    // System is stored too: with nothing stored, the default (dark) would apply instead.
    await user.click(screen.getByRole('radio', { name: 'System' }))
    expect(root.dataset.theme).toBeUndefined()
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('system')
  })

  it.each([
    ['light', 'Light', 'light'],
    ['system', 'System', undefined],
    ['sepia', 'Dark', 'dark'],
  ])('starts from a saved %j', (saved, checked, dataTheme) => {
    localStorage.setItem(THEME_STORAGE_KEY, saved)
    render(<ThemeToggle />)
    expect(screen.getByRole('radio', { name: checked })).toBeChecked()
    expect(root.dataset.theme).toBe(dataTheme)
  })

  it('still works when storage is blocked', async () => {
    blockStorage()
    const user = userEvent.setup()
    render(<ThemeToggle />)
    expect(root.dataset.theme).toBe('dark')
    await user.click(screen.getByRole('radio', { name: 'Light' }))
    expect(root.dataset.theme).toBe('light')
  })

  it('moves between options with the arrow keys', async () => {
    const user = userEvent.setup()
    render(<ThemeToggle />)
    await user.click(screen.getByRole('radio', { name: 'Light' }))
    await user.keyboard('{ArrowRight}')
    expect(screen.getByRole('radio', { name: 'Dark' })).toBeChecked()
  })
})

// The inline script in index.html applies the theme before the app loads, so there is no flash.
// It must reach the same result as useTheme for every stored value.
describe('index.html theme script', () => {
  const source = /<script>([\s\S]*?)<\/script>/.exec(indexHtml)?.[1] ?? ''
  const runScript = () => new Function(source)()

  it.each([
    [null, 'dark'],
    ['dark', 'dark'],
    ['light', 'light'],
    ['system', undefined],
    ['sepia', 'dark'],
  ])('with %j saved, sets data-theme to %j', (saved, expected) => {
    if (saved !== null) localStorage.setItem(THEME_STORAGE_KEY, saved)
    runScript()
    expect(root.dataset.theme).toBe(expected)
  })

  it('falls back to dark when storage is blocked', () => {
    blockStorage()
    runScript()
    expect(root.dataset.theme).toBe('dark')
  })

  it('uses the same storage key as useTheme', () => {
    expect(source).toContain(`'${THEME_STORAGE_KEY}'`)
  })
})
