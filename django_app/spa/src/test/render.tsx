import { QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router'

import { App } from '../App'
import { createQueryClient } from '../queryClient'

/** Render the whole app at `path` (relative to /app), with a fresh cache. */
export function renderApp(path = '/') {
  const queryClient = createQueryClient()
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return { ...utils, queryClient }
}
