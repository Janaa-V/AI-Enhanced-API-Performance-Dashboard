import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import App from './App'

it('renders the dashboard heading', () => {
  render(<App />)
  expect(screen.getByRole('heading', { name: 'API Performance Dashboard' })).toBeInTheDocument()
})
