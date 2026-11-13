import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, unwrap } from '../../api/client'
import type { PatchedSessionRequest, Session, SessionRequest } from '../../api/types'
import { invalidateBalances } from '../payees/queries'
import { toOneOffBooking, toRecurringBooking, type ScheduleFormValues } from './scheduleForm'

export type SessionStatus = 'all' | 'logged' | 'unlogged'
export type SessionPeriod = 'all' | 'past' | 'today' | 'future'

export const sessionKeys = {
  all: ['sessions'] as const,
  calendar: (status: SessionStatus, period: SessionPeriod, q: string) => ['sessions', 'calendar', status, period, q] as const,
  detail: (id: string) => ['sessions', 'detail', id] as const,
}

/** The Tutoring calendar's events, with whether each has been logged. */
export function useCalendarSessions(status: SessionStatus, period: SessionPeriod, q: string) {
  return useQuery({
    queryKey: sessionKeys.calendar(status, period, q),
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/calendar/sessions', { params: { query: { status, period, ...(q && { q }) } } })),
  })
}

export function useSession(id: string) {
  return useQuery({
    queryKey: sessionKeys.detail(id),
    queryFn: async () => unwrap(await api.GET('/api/v1/sessions/{id}/', { params: { path: { id } } })),
  })
}

/**
 * Logging or changing a session affects the sessions list (logged status),
 * the student's recent sessions, payee balances and the dashboard, so refresh them all.
 */
function invalidateAfterChange(queryClient: ReturnType<typeof useQueryClient>) {
  return Promise.all([
    queryClient.invalidateQueries({ queryKey: sessionKeys.all }),
    queryClient.invalidateQueries({ queryKey: ['students', 'detail'] }),
    invalidateBalances(queryClient),
  ])
}

export function useCreateSession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: SessionRequest) => unwrap(await api.POST('/api/v1/sessions/', { body })),
    onSuccess: () => invalidateAfterChange(queryClient),
  })
}

export function useUpdateSession(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: PatchedSessionRequest) =>
      unwrap(await api.PATCH('/api/v1/sessions/{id}/', { params: { path: { id } }, body })),
    onSuccess: (session) => {
      queryClient.setQueryData<Session>(sessionKeys.detail(id), session)
      return invalidateAfterChange(queryClient)
    },
  })
}

export function useDeleteSession(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      unwrap(await api.DELETE('/api/v1/sessions/{id}/', { params: { path: { id } } }))
    },
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: sessionKeys.detail(id) })
      return invalidateAfterChange(queryClient)
    },
  })
}

export function useZoomParse() {
  return useMutation({
    mutationFn: async (summary: string) => unwrap(await api.POST('/api/v1/sessions/zoom-parse/', { body: { summary } })),
  })
}

/** Log any Zoom lessons from the last week that TutorHub missed (including no-shows). */
export function useZoomSweep() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => unwrap(await api.POST('/api/v1/zoom/sweep')),
    onSuccess: () => invalidateAfterChange(queryClient),
  })
}

/** Fetch a saved session's AI Companion summary from Zoom. Nothing is saved. */
export function useZoomFetch(sessionId: string) {
  return useMutation({
    mutationFn: async () => unwrap(await api.GET('/api/v1/sessions/{id}/zoom-summary/', { params: { path: { id: sessionId } } })),
  })
}

/**
 * Book lessons on Google Calendar: one event, or one weekly event per chosen
 * day. Resolves to how many events were asked for and how many Google made
 * (it can quietly refuse some of a weekly booking).
 */
export function useBookLessons() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (values: ScheduleFormValues) => {
      if (values.kind === 'oneoff') {
        unwrap(await api.POST('/api/v1/calendar/events', { body: toOneOffBooking(values) }))
        return { requested: 1, created: 1 }
      }
      const body = toRecurringBooking(values)
      const events = unwrap(await api.POST('/api/v1/calendar/events/recurring', { body }))
      return { requested: body.day_configs.length, created: events.length }
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: sessionKeys.all }),
  })
}
