import { QueryClientProvider } from '@tanstack/react-query'
import { render, renderHook } from '@testing-library/react'
import type { ReactElement, ReactNode } from 'react'
import { createQueryClient } from '../hooks/queryClient'

// A fresh client per test, with the app's defaults but no retries, so a failure shows at once.
function setup() {
  const client = createQueryClient({ retry: false })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  return { client, wrapper }
}

export function renderWithClient(ui: ReactElement) {
  const { client, wrapper } = setup()
  return { client, ...render(ui, { wrapper }) }
}

export function renderHookWithClient<Result, Props>(
  hook: (props: Props) => Result,
  initialProps?: Props,
) {
  const { client, wrapper } = setup()
  return { client, ...renderHook(hook, { wrapper, initialProps }) }
}
