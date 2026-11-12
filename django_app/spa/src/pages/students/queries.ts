/**
 * Students data. Query keys are arrays, so related data shares a prefix:
 * ['students'] is every student query, ['students', 'list', q] one search,
 * ['students', 'detail', id] one student. After a change, invalidating
 * ['students'] marks all of them stale, and whatever is on screen refetches.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, unwrap } from '../../api/client'
import type { Student, StudentRequest } from '../../api/types'
import { invalidateBalances } from '../payees/queries'

export const studentKeys = {
  all: ['students'] as const,
  list: (q: string) => ['students', 'list', q] as const,
  detail: (id: string) => ['students', 'detail', id] as const,
  sessions: (id: string) => ['students', 'detail', id, 'sessions'] as const,
}

export function useStudents(q: string) {
  return useQuery({
    queryKey: studentKeys.list(q),
    queryFn: async () => unwrap(await api.GET('/api/v1/students/', { params: { query: q ? { q } : {} } })),
  })
}

export function useStudent(id: string) {
  return useQuery({
    queryKey: studentKeys.detail(id),
    queryFn: async () => unwrap(await api.GET('/api/v1/students/{id}/', { params: { path: { id } } })),
  })
}

export function useRecentSessions(studentId: string) {
  return useQuery({
    queryKey: studentKeys.sessions(studentId),
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/sessions/', { params: { query: { student: studentId, limit: 10 } } })),
  })
}

export function useCreateStudent() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: StudentRequest) => unwrap(await api.POST('/api/v1/students/', { body })),
    onSuccess: () => Promise.all([queryClient.invalidateQueries({ queryKey: studentKeys.all }), invalidateBalances(queryClient)]),
  })
}

export function useUpdateStudent(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: StudentRequest) =>
      unwrap(await api.PATCH('/api/v1/students/{id}/', { params: { path: { id } }, body })),
    onSuccess: (student) => {
      // We already have the updated student, so put it straight in the cache.
      queryClient.setQueryData<Student>(studentKeys.detail(id), student)
      return Promise.all([queryClient.invalidateQueries({ queryKey: ['students', 'list'] }), invalidateBalances(queryClient)])
    },
  })
}

export function useToggleActive(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () =>
      unwrap(await api.POST('/api/v1/students/{id}/toggle-active/', { params: { path: { id } } })),
    onSuccess: (student) => {
      queryClient.setQueryData<Student>(studentKeys.detail(id), student)
      return queryClient.invalidateQueries({ queryKey: ['students', 'list'] })
    },
  })
}

export function useDeleteStudent(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      unwrap(await api.DELETE('/api/v1/students/{id}/', { params: { path: { id } } }))
    },
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: studentKeys.detail(id) })
      return Promise.all([queryClient.invalidateQueries({ queryKey: ['students', 'list'] }), invalidateBalances(queryClient)])
    },
  })
}
