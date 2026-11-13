import { useQuery } from '@tanstack/react-query'

import { api, unwrap } from '../../api/client'

// Each panel has its own request, so a slow one doesn't hold up the others.

export function useDashboardStats() {
  return useQuery({
    queryKey: ['dashboard'],
    queryFn: async () => unwrap(await api.GET('/api/v1/analytics/dashboard')),
  })
}

export function useRevenueByMonth() {
  return useQuery({
    queryKey: ['dashboard', 'revenue'],
    queryFn: async () => unwrap(await api.GET('/api/v1/analytics/dashboard/revenue')).months,
  })
}

export function useUpcomingSessions(days = 4) {
  return useQuery({
    queryKey: ['dashboard', 'upcoming', days],
    queryFn: async () => unwrap(await api.GET('/api/v1/analytics/dashboard/upcoming', { params: { query: { days } } })).sessions,
  })
}

export function useStudentBreakdown() {
  return useQuery({
    queryKey: ['dashboard', 'students'],
    queryFn: async () => unwrap(await api.GET('/api/v1/analytics/dashboard/students')).students,
  })
}
