import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll, vi } from 'vitest'

import { server } from './server'

// jsdom can't draw on a <canvas>, so the dashboard's chart is a labelled stand-in.
vi.mock('../pages/dashboard/RevenueChart', async () => {
  const { createElement } = await import('react')
  return {
    RevenueChart: ({ months }: { months: unknown[] }) =>
      createElement('div', { role: 'img', 'aria-label': 'Revenue for each of the last 12 months', 'data-months': months.length }),
  }
})

// Any request without a handler fails the test, rather than reaching the network.
beforeAll(() => server.listen({ onUnhandledFrame: 'error' }))

afterEach(() => {
  cleanup()
  server.resetHandlers()
  document.cookie = 'csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT'
  document.documentElement.classList.remove('dark')
  localStorage.clear()
})

afterAll(() => server.close())
