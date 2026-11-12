/**
 * Who is logged in, as React Query state.
 *
 * The cookies are httponly, so the app can't look at them to tell whether
 * you're logged in. Instead it asks the server (GET /auth/me) and caches the
 * answer under the ['me'] key: a User, or null when logged out. Logging in or
 * out just updates that cache entry, and every component reading it re-renders.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, unwrap } from './api/client'
import type { User } from './api/types'

export const meQueryKey = ['me'] as const

export function useMe() {
  return useQuery({
    queryKey: meQueryKey,
    queryFn: async (): Promise<User | null> => {
      const result = await api.GET('/api/v1/auth/me')
      // The client has already tried refreshing an expired login by now, so
      // a 401 really means "logged out".
      if (result.response.status === 401) return null
      return unwrap(result)
    },
    staleTime: Infinity,
  })
}

export function useLogin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (credentials: { email: string; password: string }) =>
      unwrap(await api.POST('/api/v1/auth/cookie/login', { body: credentials })),
    onSuccess: (user) => queryClient.setQueryData(meQueryKey, user),
  })
}

export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      await api.POST('/api/v1/auth/cookie/logout')
    },
    onSuccess: () => {
      // Forget everything fetched as this user, then mark us logged out.
      queryClient.clear()
      queryClient.setQueryData(meQueryKey, null)
    },
  })
}
