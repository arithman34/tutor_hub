import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, unwrap } from '../../api/client'
import { leaveFor } from '../../browser'
import { sessionKeys } from '../sessions/queries'

export const calendarStatusKey = ['calendar', 'status'] as const

export function useCalendarStatus() {
  return useQuery({
    queryKey: calendarStatusKey,
    queryFn: async () => unwrap(await api.GET('/api/v1/calendar/status')),
  })
}

/**
 * Start connecting Google: ask the server for Google's consent page, then
 * leave the app for it. Google sends the browser back to /app/connections
 * with ?connected=1 or ?error=… once the user has answered.
 */
export function useConnectGoogle() {
  return useMutation({
    mutationFn: async () => unwrap(await api.GET('/api/v1/calendar/connect')),
    onSuccess: ({ url }) => leaveFor(url),
  })
}

export function useDisconnectGoogle() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      unwrap(await api.POST('/api/v1/calendar/disconnect'))
    },
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: calendarStatusKey }),
        // The sessions list comes from the calendar, so it changes too.
        queryClient.invalidateQueries({ queryKey: sessionKeys.all }),
      ]),
  })
}
