import { QueryClient } from '@tanstack/react-query'

import { ApiError } from './api/client'

export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Retry network blips and server errors once, but not 4xx answers:
        // asking again won't change a 403 or 404.
        retry: (failureCount, error) => !(error instanceof ApiError && error.status < 500) && failureCount < 1,
      },
    },
  })
}
