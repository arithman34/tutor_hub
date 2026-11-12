import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, unwrap } from '../../api/client'
import type { components } from '../../api/schema'

export const setupStatusKey = ['setup'] as const

/** Whether this TutorHub has no account yet, so first-run setup should show. */
export function useSetupStatus() {
  return useQuery({
    queryKey: setupStatusKey,
    queryFn: async () => unwrap(await api.GET('/api/v1/setup')),
    staleTime: Infinity,
  })
}

export function useCreateFirstAccount() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: components['schemas']['SetupRequest']) => unwrap(await api.POST('/api/v1/setup', { body })),
    onSuccess: () => queryClient.setQueryData(setupStatusKey, { needed: false }),
  })
}
