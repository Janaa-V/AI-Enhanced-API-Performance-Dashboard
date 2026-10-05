import { QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/tokens.css'
import './styles/global.css'
import App from './App'
import { createQueryClient } from './hooks/queryClient'

const root = document.getElementById('root')
if (!root) {
  throw new Error('index.html is missing <div id="root">')
}

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={createQueryClient()}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
